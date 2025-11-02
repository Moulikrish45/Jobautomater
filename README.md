# Job Application Automation Platform

An AI-powered job application automation platform that collects user details and preferences once, then continuously searches job portals and applies to relevant positions using browser automation and APIs.

## Features

- **Privacy-focused**: All data stored locally, no external data transmission except for job applications
- **Multi-portal support**: LinkedIn, Indeed, Naukri job search automation
- **AI-powered resume optimization**: Tailors resumes for each job application using local AI models
- **Browser automation**: Automated form filling and application submission
- **Comprehensive tracking**: Dashboard for monitoring application status and analytics

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd job-application-automation
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Start infrastructure services**
   ```bash
   docker-compose up -d mongodb redis
   ```

6. **Run the application**
   ```bash
   # Start FastAPI server
   uvicorn app.main:app --reload --port 8000
   
   # In another terminal, start Celery worker
   celery -A app.celery_app worker --loglevel=info
   ```

7. **Access the application**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Production Deployment

```bash
# Start all services including the application
docker-compose --profile production up -d
```

## Project Structure

```
job-application-automation/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # MongoDB connection
│   └── celery_app.py        # Celery configuration
├── docker-compose.yml       # Docker services
├── Dockerfile              # Application container
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## API Endpoints

- `GET /` - Root endpoint with application info
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation

## Development

### Running Tests

```bash
pytest
```

### Code Style

This project follows PEP 8 style guidelines. Use tools like `black` and `flake8` for code formatting and linting.

## License

This project is licensed under the MIT License.