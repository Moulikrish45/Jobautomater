// MongoDB initialization script
db = db.getSiblingDB('job_automation');

// Create collections with basic indexes
db.createCollection('users');
db.createCollection('jobs');
db.createCollection('applications');
db.createCollection('resumes');

// Create indexes for better performance
db.users.createIndex({ "email": 1 }, { unique: true });
db.jobs.createIndex({ "external_id": 1, "portal": 1 }, { unique: true });
db.jobs.createIndex({ "user_id": 1, "status": 1 });
db.applications.createIndex({ "user_id": 1, "job_id": 1 });
db.applications.createIndex({ "status": 1, "created_at": -1 });
db.resumes.createIndex({ "user_id": 1, "job_id": 1 });

print('Database initialized successfully');