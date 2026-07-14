import os
import csv
import io
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from celery.schedules import crontab
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from celery import Celery
from flask_caching import Cache

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Put this right after app = Flask(__name__)
app.config['CACHE_TYPE'] = 'RedisCache'
app.config['CACHE_REDIS_URL'] = 'redis://localhost:6379/1'
cache = Cache(app)




app.config['SECRET_KEY'] = 'super-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'placement_portal.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'placement-portal-super-secret-jwt-key'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False

app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
app.config['CELERY_TIMEZONE'] = 'Asia/Kolkata'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

SENDER_EMAIL = "nytsneha@gmail.com"      
APP_PASSWORD = "beie aqhg jewy cqri"   
ADMIN_EMAIL = "nytsneha@gmail.com" 

@celery.task
def send_email_async(student_email, student_name, company_name, status):
    msg = EmailMessage()
    msg['Subject'] = f"Update: Your application at {company_name}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = student_email
    
    text_content = f"Dear {student_name},\n\nYour application status at {company_name} has been updated to: {status}.\n\nPlease log in to your dashboard for details."
    msg.set_content(text_content)
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        pass

@celery.task
def send_offer_letter_async(student_email, student_name, company_name, job_title):
    msg = EmailMessage()
    msg['Subject'] = f"Official Offer Letter: {company_name} - {job_title}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = student_email
    
    text_content = f"Dear {student_name},\n\nCongratulations! We are delighted to formally offer you the position of {job_title} at {company_name}.\n\nWelcome to the team!"
    msg.set_content(text_content)
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        pass

@celery.task
def export_csv_async(student_id, student_email, student_name):
    with app.app_context():
        apps = Application.query.filter_by(student_id=student_id).all()
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['Student ID', 'Company Name', 'Job Title', 'Application Status', 'Application Date'])
        
        for a in apps:
            cw.writerow([student_id, a.drive.company.company_name, a.drive.job_title, a.status, a.application_date.strftime('%Y-%m-%d')])
        
        csv_data = si.getvalue()
        
        msg = EmailMessage()
        msg['Subject'] = "Your Placement Application History (CSV Report)"
        msg['From'] = SENDER_EMAIL
        msg['To'] = student_email
        msg.set_content("Please find your CSV export attached.")
        msg.add_attachment(csv_data.encode('utf-8'), maintype='text', subtype='csv', filename='Placement_History_Report.csv')
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(SENDER_EMAIL, APP_PASSWORD)
                smtp.send_message(msg)
        except Exception:
            pass

@celery.task
def send_daily_reminders():
    with app.app_context():
        upcoming_deadline = datetime.utcnow() + timedelta(days=3)
        drives = PlacementDrive.query.filter(PlacementDrive.status == 'Approved', PlacementDrive.application_deadline <= upcoming_deadline, PlacementDrive.application_deadline >= datetime.utcnow()).all()
        
        if not drives:
            return "No upcoming deadlines."

        drive_list_text = ""
        for d in drives:
            drive_list_text += f"- {d.job_title} at {d.company.company_name} (Closes: {d.application_deadline.strftime('%Y-%m-%d')})\n"
            
        students = Student.query.all()
        for student in students:
            msg = EmailMessage()
            msg['Subject'] = "Reminder: Placement Drives Closing Soon!"
            msg['From'] = SENDER_EMAIL
            msg['To'] = student.user.email
            
            text_content = f"Hello {student.fullname},\n\nThe following drives are closing soon:\n{drive_list_text}\nPlease log in to apply."
            msg.set_content(text_content)
            
            try:
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
            except Exception:
                pass

@celery.task
def send_monthly_report():
    with app.app_context():
        total_drives = PlacementDrive.query.count()
        total_applied = Application.query.count()
        total_selected = Application.query.filter_by(status='Selected').count()
        
        msg = EmailMessage()
        msg['Subject'] = "Admin Alert: Monthly Placement Statistics"
        msg['From'] = SENDER_EMAIL
        msg['To'] = ADMIN_EMAIL
        
        text_content = f"Monthly Stats:\nTotal Drives: {total_drives}\nTotal Applications: {total_applied}\nTotal Selected: {total_selected}"
        msg.set_content(text_content)
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(SENDER_EMAIL, APP_PASSWORD)
                smtp.send_message(msg)
        except Exception: 
            pass

celery.conf.CELERYBEAT_SCHEDULE = {
    'daily-student-reminders': { 'task': 'app.send_daily_reminders', 'schedule': crontab(minute='*') },
    'monthly-admin-report': { 'task': 'app.send_monthly_report', 'schedule': crontab(minute='*') }
}

db = SQLAlchemy(app)
jwt = JWTManager(app)
CORS(app)

@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    return jsonify({"message": f"Invalid token: {error_string}"}), 422

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  
    is_blacklisted = db.Column(db.Boolean, default=False)
    student_profile = db.relationship('Student', backref='user', uselist=False)
    company_profile = db.relationship('CompanyProfile', backref='user', uselist=False)

class Student(db.Model):
    student_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    fullname = db.Column(db.String(100), nullable=False)
    cgpa = db.Column(db.Float, nullable=True)
    branch = db.Column(db.String(50))
    graduation_year = db.Column(db.Integer) 
    resume_link = db.Column(db.String(200))

class CompanyProfile(db.Model):
    company_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    hr_contact = db.Column(db.String(100)) 
    website = db.Column(db.String(100))
    approval_status = db.Column(db.String(20), default='Pending')

class PlacementDrive(db.Model):
    drive_id = db.Column(db.Integer, primary_key=True) 
    company_id = db.Column(db.Integer, db.ForeignKey('company_profile.company_id'), nullable=False)
    job_title = db.Column(db.String(100), nullable=False) 
    job_description = db.Column(db.Text) 
    eligibility_cgpa = db.Column(db.Float) 
    eligibility_branch = db.Column(db.String(100)) 
    eligibility_year = db.Column(db.Integer) 
    application_deadline = db.Column(db.DateTime) 
    status = db.Column(db.String(20), default='Pending') 
    company = db.relationship('CompanyProfile', backref='drives')

class Application(db.Model):
    application_id = db.Column(db.Integer, primary_key=True) 
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False) 
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drive.drive_id'), nullable=False) 
    application_date = db.Column(db.DateTime, default=datetime.utcnow) 
    status = db.Column(db.String(20), default='Applied') 
    drive = db.relationship('PlacementDrive', backref='applications')
    student = db.relationship('Student', backref='applications')

with app.app_context():
    db.create_all()
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        new_admin = User(username='admin', email='admin@institute.edu', password_hash=generate_password_hash('admin123'), role='admin')
        db.session.add(new_admin)
        db.session.commit()

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data.get('username')).first()
    
    if user and check_password_hash(user.password_hash, data.get('password')):
        if user.is_blacklisted: 
            return jsonify({'message': 'Blacklisted by Institute.'}), 403
            
        access_token = create_access_token(identity=str(user.user_id), additional_claims={'role': user.role, 'username': user.username})
        return jsonify({'token': access_token, 'role': user.role}), 200
        
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({'message': 'Username exists'}), 400
            
        new_user = User(
            username=data['username'], 
            email=data['email'], 
            password_hash=generate_password_hash(data['password']), 
            role=data['role']
        )
        db.session.add(new_user)
        db.session.flush() 
        
        if data['role'] == 'student':
            new_student = Student(
                user_id=new_user.user_id, 
                fullname=data['fullname'], 
                cgpa=float(data.get('cgpa')), 
                branch=data.get('branch'), 
                graduation_year=data.get('graduation_year')
            )
            db.session.add(new_student)
            
        elif data['role'] == 'company':
            new_company = CompanyProfile(
                user_id=new_user.user_id, 
                company_name=data.get('company_name'), 
                hr_contact=data.get('hr_contact'), 
                website=data.get('website'), 
                approval_status='Pending'
            )
            db.session.add(new_company)
            
        db.session.commit()
        return jsonify({'message': 'Registered successfully'}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Server Error'}), 500

@app.route('/api/admin/stats', methods=['GET'])
@jwt_required()
@cache.cached(timeout=30)
def admin_stats(): 
    students_count = Student.query.count()
    companies_count = CompanyProfile.query.count()
    drives_count = PlacementDrive.query.count()
    return jsonify({'students': students_count, 'companies': companies_count, 'drives': drives_count})

@app.route('/api/admin/companies', methods=['GET'])
@jwt_required()
def admin_companies(): 
    companies = CompanyProfile.query.all()
    company_list = []
    for c in companies:
        company_list.append({
            'company_id': c.company_id, 
            'company_name': c.company_name, 
            'approval_status': c.approval_status
        })
    return jsonify(company_list)

@app.route('/api/admin/approve_company/<int:company_id>', methods=['POST'])
@jwt_required()
def approve_company(company_id):
    c = CompanyProfile.query.get_or_404(company_id)
    c.approval_status = 'Approved'
    db.session.commit()
    return jsonify({'message': 'Approved'})

@app.route('/api/admin/reject_company/<int:company_id>', methods=['POST'])
@jwt_required()
def reject_company(company_id):
    c = CompanyProfile.query.get_or_404(company_id)
    db.session.delete(c.user)
    db.session.delete(c)
    db.session.commit()
    return jsonify({'message': 'Rejected'})

@app.route('/api/admin/pending_drives', methods=['GET'])
@jwt_required()
def get_pending_drives(): 
    drives = PlacementDrive.query.filter_by(status='Pending').all()
    drive_list = []
    for d in drives:
        drive_list.append({
            'drive_id': d.drive_id, 
            'job_title': d.job_title, 
            'company': d.company.company_name, 
            'application_deadline': d.application_deadline.strftime('%Y-%m-%d')
        })
    return jsonify(drive_list)

@app.route('/api/admin/all_drives', methods=['GET'])
@jwt_required()
def admin_all_drives(): 
    drives = PlacementDrive.query.all()
    drive_list = []
    for d in drives:
        drive_list.append({
            'drive_id': d.drive_id, 
            'job_title': d.job_title, 
            'company': d.company.company_name, 
            'application_deadline': d.application_deadline.strftime('%Y-%m-%d'), 
            'status': d.status
        })
    return jsonify(drive_list)

@app.route('/api/admin/drive/<int:drive_id>/<action>', methods=['POST'])
@jwt_required()
def process_drive(drive_id, action):
    d = PlacementDrive.query.get_or_404(drive_id)
    if action == 'approve': 
        d.status = 'Approved'
    elif action == 'reject': 
        d.status = 'Rejected'
    elif action == 'close': 
        d.status = 'Closed'
    db.session.commit()
    return jsonify({'message': f'Drive updated'})

@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
def get_all_users():
    user_list = []
    
    students = Student.query.all()
    for s in students:
        user_list.append({
            'user_id': s.user.user_id, 
            'name': s.fullname, 
            'type': 'Student', 
            'email': s.user.email, 
            'is_blacklisted': s.user.is_blacklisted
        })
        
    companies = CompanyProfile.query.filter_by(approval_status='Approved').all()
    for c in companies:
        user_list.append({
            'user_id': c.user.user_id, 
            'name': c.company_name, 
            'type': 'Company', 
            'email': c.user.email, 
            'is_blacklisted': c.user.is_blacklisted
        })
        
    return jsonify(user_list)

@app.route('/api/admin/user/<int:user_id>/toggle_blacklist', methods=['POST'])
@jwt_required()
def toggle_blacklist(user_id):
    u = User.query.get_or_404(user_id)
    if u.role == 'admin': 
        return jsonify({'message': 'Cannot blacklist admin'}), 400
    u.is_blacklisted = not u.is_blacklisted
    db.session.commit()
    return jsonify({'message': 'Updated'})

@app.route('/api/admin/applications', methods=['GET'])
@jwt_required()
def get_all_applications(): 
    applications = Application.query.all()
    app_list = []
    for a in applications:
        app_list.append({
            'application_id': a.application_id, 
            'student': a.student.fullname, 
            'company': a.drive.company.company_name, 
            'job_title': a.drive.job_title, 
            'status': a.status
        })
    return jsonify(app_list)

@app.route('/api/company/drives', methods=['GET', 'POST'])
@jwt_required()
def company_drives():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    c = user.company_profile
    
    if request.method == 'POST':
        if c.approval_status != 'Approved': 
            return jsonify({'message': 'Not approved'}), 403
            
        data = request.json
        new_drive = PlacementDrive(
            company_id=c.company_id, 
            job_title=data['job_title'], 
            job_description=data['job_description'], 
            eligibility_cgpa=float(data['eligibility_cgpa']), 
            eligibility_branch=data['eligibility_branch'], 
            eligibility_year=int(data['eligibility_year']), 
            application_deadline=datetime.strptime(data['application_deadline'], '%Y-%m-%d')
        )
        db.session.add(new_drive)
        db.session.commit()
        return jsonify({'message': 'Created'}), 201
        
    drives = PlacementDrive.query.filter_by(company_id=c.company_id).all()
    drive_list = []
    for d in drives:
        drive_list.append({
            'drive_id': d.drive_id, 
            'job_title': d.job_title, 
            'status': d.status,
            'applicant_count': len(d.applications)
        })

    company_details = {
        'company_name': c.company_name,
        'hr_contact': c.hr_contact,
        'website': c.website,
        'approval_status': c.approval_status
    }
    return jsonify({
        'drives': drive_list, 
        'profile': company_details

   })

@app.route('/api/company/drive/<int:drive_id>/applicants', methods=['GET'])
@jwt_required()
def drive_applicants(drive_id): 
    applications = Application.query.filter_by(drive_id=drive_id).all()
    app_list = []
    for a in applications:
        app_list.append({
            'application_id': a.application_id, 
            'student_name': a.student.fullname, 
            'cgpa': a.student.cgpa, 
            'status': a.status, 
            'resume_link': a.student.resume_link
        })
    return jsonify(app_list)

@app.route('/api/company/application/<int:application_id>/status', methods=['POST'])
@jwt_required()
def update_app_status(application_id):
    a = Application.query.get_or_404(application_id)
    a.status = request.json['status']
    db.session.commit()
    send_email_async.delay(a.student.user.email, a.student.fullname, a.drive.company.company_name, a.status)
    return jsonify({'message': 'Updated'})

@app.route('/api/company/application/<int:application_id>/send_offer', methods=['POST'])
@jwt_required()
def send_offer_email(application_id):
    a = Application.query.get_or_404(application_id)
    if a.status != 'Selected':
        return jsonify({'message': 'Student must be Selected'}), 400
    
    send_offer_letter_async.delay(a.student.user.email, a.student.fullname, a.drive.company.company_name, a.drive.job_title)
    return jsonify({'message': 'Offer sent'})

@app.route('/api/student/drives', methods=['GET'])
@jwt_required()
def student_drives(): 
    drives = PlacementDrive.query.filter_by(status='Approved').all()
    drive_list = []
    for d in drives:
        drive_list.append({
            'drive_id': d.drive_id, 
            'job_title': d.job_title, 
            'company': d.company.company_name, 
            'eligibility_cgpa': d.eligibility_cgpa, 
            'eligibility_branch': d.eligibility_branch,
            'application_deadline': d.application_deadline.strftime('%Y-%m-%d')
        })
    return jsonify(drive_list)

@app.route('/api/student/apply/<int:drive_id>', methods=['POST'])
@jwt_required()
def apply_drive(drive_id):
    user_id = int(get_jwt_identity())
    s = User.query.get(user_id).student_profile
    d = PlacementDrive.query.get_or_404(drive_id)
    
    if s.cgpa < d.eligibility_cgpa: 
        return jsonify({'message': 'CGPA requirement not met '}), 403
        
    existing_app = Application.query.filter_by(student_id=s.student_id, drive_id=drive_id).first()
    if existing_app: 
        return jsonify({'message': 'Already applied'}), 400
        
    new_app = Application(student_id=s.student_id, drive_id=drive_id)
    db.session.add(new_app)
    db.session.commit()
    return jsonify({'message': 'Applied'})

@app.route('/api/student/applications', methods=['GET'])
@jwt_required()
def my_applications(): 
    user_id = int(get_jwt_identity())
    student_id = User.query.get(user_id).student_profile.student_id
    applications = Application.query.filter_by(student_id=student_id).all()
    
    app_list = []
    for a in applications:
        app_list.append({
            'company': a.drive.company.company_name, 
            'job_title': a.drive.job_title, 
            'status': a.status, 
            'application_date': a.application_date.strftime('%Y-%m-%d')
        })
    return jsonify(app_list)

@app.route('/api/student/profile', methods=['GET', 'PUT'])
@jwt_required()
def student_profile():
    user_id = int(get_jwt_identity())
    s = User.query.get(user_id).student_profile
    
    if request.method == 'PUT':
        data = request.json
        s.fullname = data['fullname']
        s.cgpa = float(data['cgpa'])
        s.branch = data['branch']
        s.graduation_year = data['graduation_year']
        s.resume_link = data['resume_link']
        db.session.commit()
        return jsonify({'message': 'Updated'})
        
    return jsonify({
        'fullname': s.fullname, 
        'cgpa': s.cgpa, 
        'branch': s.branch, 
        'graduation_year': s.graduation_year, 
        'resume_link': s.resume_link or ''
    })

@app.route('/api/student/export_applications', methods=['POST'])
@jwt_required()
def export_applications():
    user = User.query.get(int(get_jwt_identity()))
    export_csv_async.delay(user.student_profile.student_id, user.email, user.student_profile.fullname)
    return jsonify({"message": "Export started"})

@app.route('/api/admin/search', methods=['GET'])
@jwt_required()
def admin_search():
    query_string = request.args.get('q', '')
    search_pattern = f"%{query_string}%"
    
    matching_users = User.query.filter(User.username.ilike(search_pattern)).all()
    
    search_results = []
    for user in matching_users:
        search_results.append({
            'user_id': user.user_id,
            'name': user.username,
            'email': user.email,
            'type': user.role.capitalize(),
            'is_blacklisted': user.is_blacklisted
        })
        
    return jsonify(search_results)

if __name__ == '__main__':
    app.run(debug=True)