#!/usr/bin/env python3
"""
Test script for the Auto-Applier User Flow implementation.
This script tests the core functionality without requiring a full setup.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

async def test_portal_strategies():
    """Test portal strategy detection and basic functionality."""
    print("🧪 Testing Portal Strategies...")
    
    try:
        from app.services.portal_strategies import portal_strategy_manager
        
        # Test portal detection
        test_urls = [
            "https://www.linkedin.com/jobs/view/123456",
            "https://www.indeed.com/viewjob?jk=abcd1234",
            "https://www.glassdoor.com/job-listing/123",
            "https://example.com/careers/job/456"
        ]
        
        for url in test_urls:
            portal = portal_strategy_manager.detect_portal(url)
            strategy = portal_strategy_manager.get_strategy(url)
            print(f"  ✅ URL: {url}")
            print(f"     Portal: {portal}")
            print(f"     Strategy: {strategy.__class__.__name__}")
        
        print("✅ Portal strategies test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Portal strategies test failed: {e}")
        return False


async def test_application_models():
    """Test application models and enums."""
    print("\n🧪 Testing Application Models...")
    
    try:
        from app.models.application import ApplicationStatus, ApplicationOutcome, Application
        
        # Test enums
        print(f"  ✅ ApplicationStatus values: {list(ApplicationStatus)}")
        print(f"  ✅ ApplicationOutcome values: {list(ApplicationOutcome)}")
        
        # Test model creation (without database)
        from datetime import datetime
        from bson import ObjectId
        
        # This would normally require database connection, so we'll just test imports
        print("  ✅ Application model imported successfully")
        
        print("✅ Application models test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Application models test failed: {e}")
        return False


async def test_browser_automation_service():
    """Test browser automation service initialization."""
    print("\n🧪 Testing Browser Automation Service...")
    
    try:
        from app.services.browser_automation_service import BrowserAutomationService
        
        # Test service creation
        service = BrowserAutomationService()
        print("  ✅ BrowserAutomationService created")
        
        # Test method existence
        assert hasattr(service, 'apply_to_job'), "apply_to_job method missing"
        assert hasattr(service, 'initialize'), "initialize method missing"
        assert hasattr(service, 'create_session'), "create_session method missing"
        
        print("  ✅ Required methods exist")
        print("✅ Browser automation service test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Browser automation service test failed: {e}")
        return False


async def test_notification_service():
    """Test notification service."""
    print("\n🧪 Testing Notification Service...")
    
    try:
        from app.services.notification_service import notification_service
        
        # Test service methods
        assert hasattr(notification_service, 'send_user_notification'), "send_user_notification method missing"
        assert hasattr(notification_service, 'notify_application_queued'), "notify_application_queued method missing"
        assert hasattr(notification_service, 'notify_application_progress'), "notify_application_progress method missing"
        
        print("  ✅ Notification service methods exist")
        print("✅ Notification service test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Notification service test failed: {e}")
        return False


async def test_task_files():
    """Test that task files exist."""
    print("\n🧪 Testing Task Files...")
    
    try:
        task_files = [
            "app/tasks/application_tasks.py",
            "app/services/portal_strategies.py"
        ]
        
        for task_file in task_files:
            if Path(task_file).exists():
                print(f"  ✅ {task_file} exists")
            else:
                print(f"  ❌ {task_file} missing")
                return False
        
        # Test that the ApplicationWorker class exists in the file
        with open("app/tasks/application_tasks.py", "r") as f:
            content = f.read()
            if "class ApplicationWorker:" in content:
                print("  ✅ ApplicationWorker class found")
            else:
                print("  ❌ ApplicationWorker class missing")
                return False
        
        print("✅ Task files test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Task files test failed: {e}")
        return False


def test_frontend_components():
    """Test that frontend components exist."""
    print("\n🧪 Testing Frontend Components...")
    
    try:
        frontend_components = [
            "frontend/src/components/AutoApplyButton.tsx",
            "frontend/src/components/ApplicationDetail.tsx",
            "frontend/src/components/JobCard.tsx"
        ]
        
        for component in frontend_components:
            if Path(component).exists():
                print(f"  ✅ {component} exists")
            else:
                print(f"  ❌ {component} missing")
                return False
        
        print("✅ Frontend components test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Frontend components test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting Auto-Applier User Flow Tests\n")
    
    tests = [
        test_portal_strategies,
        test_application_models,
        test_browser_automation_service,
        test_notification_service,
        test_task_files,
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    # Test frontend components (sync)
    results.append(test_frontend_components())
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Test Summary: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The Auto-Applier User Flow implementation looks good.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)