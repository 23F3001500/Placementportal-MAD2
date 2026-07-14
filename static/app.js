const { createApp } = Vue;
const { createRouter, createWebHashHistory } = VueRouter;

const Login = {
    template: '#login-template',
    data() { 
        return { username: '', password: '' } 
    },
    methods: {
        async login() {
            try {
                const res = await axios.post('/api/login', { 
                    username: this.username, 
                    password: this.password 
                });
                localStorage.setItem('token', res.data.token);
                localStorage.setItem('role', res.data.role);
                axios.defaults.headers.common['Authorization'] = 'Bearer ' + res.data.token;
                
                this.$root.isAuthenticated = true;
                this.$root.userRole = res.data.role;
                
                if (res.data.role === 'admin') {
                    this.$router.push('/admin');
                } else if (res.data.role === 'company') {
                    this.$router.push('/company');
                } else {
                    this.$router.push('/student');
                }
            } catch (e) { 
                alert('Invalid Credentials'); 
            }
        }
    }
};

const Register = {
    template: '#register-template',
    data() { 
        return { 
            role: 'student', username: '', password: '', email: '', 
            fullname: '', cgpa: '', branch: '', graduation_year: '', 
            company_name: '', hr_contact: '', website: '' 
        } 
    },
    methods: {
        async register() {
            try {
                await axios.post('/api/register', this.$data);
                alert('Registration Successful! Please log in.');
                this.$router.push('/login');
            } catch (e) { 
                alert('Server error while registering.'); 
            }
        }
    }
};

const AdminDash = {
    template: '#admin-dash-template',
    data() { 
        return { stats: { students: 0, companies: 0, drives: 0 } } 
    },
    async mounted() {
        try {
            const res = await axios.get('/api/admin/stats');
            this.stats = res.data;
        } catch(e) {
            alert('Error loading stats');
        }
    }
};

const AdminApprovals = {
    template: '#admin-approvals-template',
    data() { 
        return { companies: [], pendingDrives: [] } 
    },
    async mounted() { 
        this.loadApprovals(); 
    },
    methods: {
        async loadApprovals() {
            const c = await axios.get('/api/admin/companies');
            this.companies = c.data;
            const d = await axios.get('/api/admin/pending_drives');
            this.pendingDrives = d.data;
        },
        async actionCompany(company_id, action) { 
            await axios.post(`/api/admin/${action}_company/${company_id}`); 
            this.loadApprovals(); 
        },
        async actionDrive(drive_id, action) { 
            await axios.post(`/api/admin/drive/${drive_id}/${action}`); 
            this.loadApprovals(); 
        }
    }
};

const AdminUsers = {
    template: '#admin-users-template',
    data() { 
        return { users: [], searchQuery: '' } 
    },
    async mounted() { 
        this.loadUsers(); 
    },
    methods: {
        async loadUsers() { 
            const res = await axios.get('/api/admin/users'); 
            this.users = res.data; 
        },
        async executeSearch() {
            if (this.searchQuery.trim() === '') {
                this.loadUsers(); 
                return;
            }
            try {
                const res = await axios.get(`/api/admin/search?q=${this.searchQuery}`);
                this.users = res.data;
            } catch (e) {
                alert('Error searching users');
            }
        },
        resetSearch() {
            this.searchQuery = '';
            this.loadUsers();
        },
        async toggleBlacklist(user_id) { 
            await axios.post(`/api/admin/user/${user_id}/toggle_blacklist`); 
            this.loadUsers(); 
        }
    }
};

const AdminDrives = {
    template: '#admin-drives-template',
    data() { 
        return { drives: [], searchQuery: '' } 
    },
    async mounted() { 
        this.loadDrives(); 
    },
    methods: {
        async loadDrives() {
            const res = await axios.get('/api/admin/all_drives');
            this.drives = res.data;
        },
        async closeDrive(drive_id) {
            await axios.post(`/api/admin/drive/${drive_id}/close`);
            this.loadDrives();
        }
    }
};

const AdminApplications = {
    template: '#admin-applications-template',
    data() { 
        return { applications: [] } 
    },
    async mounted() {
        const res = await axios.get('/api/admin/applications');
        this.applications = res.data;
    }
};

const StudentDash = {
    template: '#student-dash-template',
    data() { 
        return { drives: [], searchQuery: '' } 
    },

    computed: {
        filteredDrives() {
            if (this.searchQuery.trim() === '') {
                return this.drives;
            }
            const query = this.searchQuery.toLowerCase();
            return this.drives.filter(drive => {
                return drive.job_title.toLowerCase().includes(query) || 
                       (drive.eligibility_branch && drive.eligibility_branch.toLowerCase().includes(query));
            });
        }
    },
    async mounted() { 
        const res = await axios.get('/api/student/drives'); 
        this.drives = res.data; 
    },
    methods: {
        async apply(drive_id) {
            try { 
                await axios.post(`/api/student/apply/${drive_id}`); 
                alert('Applied successfully!'); 
            } catch (e) { 
                if (e.response && e.response.data && e.response.data.message) {
                    alert(e.response.data.message);
                } else {
                alert('Error applying'); 
            }
        }
    }
}};

const StudentApplications = {
    template: '#student-applications-template',
    data() { 
        return { applications: [] } 
    },
    async mounted() { 
        const res = await axios.get('/api/student/applications'); 
        this.applications = res.data; 
    },
    methods: {
        async exportCSV() {
            try { 
                await axios.post('/api/student/export_applications'); 
                alert("Export started! Check your email."); 
            } catch(e) { 
                alert('Error triggering CSV export.'); 
            }
        }
    }
};

const StudentProfile = {
    template: '#student-profile-template',
    data() { 
        return { profile: { fullname: '', cgpa: 0, branch: '', graduation_year: '', resume_link: '' } } 
    },
    async mounted() { 
        const res = await axios.get('/api/student/profile'); 
        this.profile = res.data; 
    },
    methods: {
        async updateProfile() {
            try { 
                await axios.put('/api/student/profile', this.profile); 
                alert('Profile updated successfully!'); 
            } catch(e) { 
                alert('Error updating profile.'); 
            }
        }
    }
};

const CompanyDash = {
    template: '#company-dash-template',
    data() { 
        return { drives: [], applicants: [], selectedDrive: null, profile: [] } 
    },
    async mounted() { 
        const res = await axios.get('/api/company/drives'); 
        this.drives = res.data.drives;  
        this.profile = res.data.profile;
    },
    methods: {
        async viewApplicants(drive_id) { 
            this.selectedDrive = drive_id; 
            const res = await axios.get(`/api/company/drive/${drive_id}/applicants`); 
            this.applicants = res.data; 
        },
        async updateStatus(application_id, status) { 
            await axios.post(`/api/company/application/${application_id}/status`, { status }); 
            this.viewApplicants(this.selectedDrive); 
        },
        async sendOfferEmail(application_id) {
            try {
                await axios.post(`/api/company/application/${application_id}/send_offer`);
                alert("Offer sent!");
            } catch(e) { 
                alert('Error sending offer letter.'); 
            }
        }
    }
};

const CompanyCreateDrive = {
    template: '#company-create-drive-template',
    data() { 
        return { form: { job_title: '', job_description: '', eligibility_cgpa: '', eligibility_branch: '', eligibility_year: '', application_deadline: '' } } 
    },
    methods: {
        async submitDrive() {
            try {
                await axios.post('/api/company/drives', this.form);
                alert('Drive created! Pending Admin approval.'); 
                this.$router.push('/company');
            } catch (e) { 
                alert('Approval pending');
            }
        }
    }
};

const routes = [
    { path: '/', redirect: '/login' },
    { path: '/login', component: Login },
    { path: '/register', component: Register },
    { path: '/admin', component: AdminDash },
    { path: '/admin/approvals', component: AdminApprovals },
    { path: '/admin/users', component: AdminUsers },
    { path: '/admin/drives', component: AdminDrives },
    { path: '/admin/applications', component: AdminApplications },
    { path: '/student', component: StudentDash },
    { path: '/student/applications', component: StudentApplications },
    { path: '/student/profile', component: StudentProfile },
    { path: '/company', component: CompanyDash },
    { path: '/company/create', component: CompanyCreateDrive },
];

const router = createRouter({ history: createWebHashHistory(), routes });

const app = createApp({
    data() { 
        return { 
            isAuthenticated: !!localStorage.getItem('token'), 
            userRole: localStorage.getItem('role') 
        } 
    },
    mounted() {
        const token = localStorage.getItem('token');
        if (token) {
            axios.defaults.headers.common['Authorization'] = 'Bearer ' + token;
        }
    },
    methods: {
        logout() { 
            localStorage.clear(); 
            this.isAuthenticated = false; 
            this.userRole = null; 
            this.$router.push('/login'); 
        }
    }
});

app.config.compilerOptions.delimiters = ['[[', ']]'];
app.use(router);
app.mount('#app');