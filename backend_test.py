import requests
import sys
import json
from datetime import datetime
import os

class InteriorDesignAITester:
    def __init__(self, base_url="https://designai-suite.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.project_id = None
        self.folder_id = None
        self.file_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        # Remove Content-Type for file uploads
        if files:
            headers.pop('Content-Type', None)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_auth_signup(self):
        """Test user signup"""
        test_user_data = {
            "name": f"Test User {datetime.now().strftime('%H%M%S')}",
            "email": f"test_{datetime.now().strftime('%H%M%S')}@example.com",
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "User Signup",
            "POST",
            "auth/signup",
            200,
            data=test_user_data
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_auth_login(self):
        """Test user login with existing credentials"""
        login_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        success, response = self.run_test(
            "User Login (fallback)",
            "POST", 
            "auth/login",
            200,
            data=login_data
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            return True
        return False

    def test_auth_me(self):
        """Test get current user"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_create_project(self):
        """Test project creation"""
        project_data = {
            "name": f"Test Project {datetime.now().strftime('%H%M%S')}"
        }
        
        success, response = self.run_test(
            "Create Project",
            "POST",
            "projects",
            200,
            data=project_data
        )
        
        if success and 'id' in response:
            self.project_id = response['id']
            print(f"   Project ID: {self.project_id}")
            return True
        return False

    def test_get_projects(self):
        """Test get all projects"""
        success, response = self.run_test(
            "Get Projects",
            "GET",
            "projects",
            200
        )
        return success

    def test_create_folder(self):
        """Test folder creation"""
        if not self.project_id:
            print("❌ No project ID available for folder creation")
            return False
            
        folder_data = {
            "name": f"Test Folder {datetime.now().strftime('%H%M%S')}"
        }
        
        success, response = self.run_test(
            "Create Folder",
            "POST",
            f"projects/{self.project_id}/folders",
            200,
            data=folder_data
        )
        
        if success and 'id' in response:
            self.folder_id = response['id']
            print(f"   Folder ID: {self.folder_id}")
            return True
        return False

    def test_get_folders(self):
        """Test get folders"""
        if not self.project_id:
            print("❌ No project ID available")
            return False
            
        success, response = self.run_test(
            "Get Folders",
            "GET",
            f"projects/{self.project_id}/folders",
            200
        )
        return success

    def test_upload_csv_file(self):
        """Test CSV file upload"""
        if not self.folder_id:
            print("❌ No folder ID available for file upload")
            return False
            
        csv_path = "/tmp/test_data.csv"
        if not os.path.exists(csv_path):
            print(f"❌ Test CSV file not found at {csv_path}")
            return False
            
        with open(csv_path, 'rb') as f:
            files = {'file': ('test_data.csv', f, 'text/csv')}
            success, response = self.run_test(
                "Upload CSV File",
                "POST",
                f"folders/{self.folder_id}/files",
                200,
                files=files
            )
            
        if success and 'id' in response:
            self.file_id = response['id']
            print(f"   File ID: {self.file_id}")
            return True
        return False

    def test_upload_pdf_file(self):
        """Test PDF file upload"""
        if not self.folder_id:
            print("❌ No folder ID available for file upload")
            return False
            
        pdf_path = "/tmp/cabinet_pricing.pdf"
        if not os.path.exists(pdf_path):
            print(f"❌ Test PDF file not found at {pdf_path}")
            return False
            
        with open(pdf_path, 'rb') as f:
            files = {'file': ('cabinet_pricing.pdf', f, 'application/pdf')}
            success, response = self.run_test(
                "Upload PDF File",
                "POST",
                f"folders/{self.folder_id}/files",
                200,
                files=files
            )
            
        return success

    def test_get_files(self):
        """Test get files"""
        if not self.folder_id:
            print("❌ No folder ID available")
            return False
            
        success, response = self.run_test(
            "Get Files",
            "GET",
            f"folders/{self.folder_id}/files",
            200
        )
        return success

    def test_get_file_details(self):
        """Test get single file details"""
        if not self.file_id:
            print("❌ No file ID available")
            return False
            
        success, response = self.run_test(
            "Get File Details",
            "GET",
            f"files/{self.file_id}",
            200
        )
        return success

    def test_save_annotation(self):
        """Test save annotation"""
        if not self.file_id:
            print("❌ No file ID available")
            return False
            
        annotation_data = {
            "annotation_json": json.dumps({
                "lines": [{"points": [10, 10, 50, 50], "stroke": "#000", "strokeWidth": 2}],
                "rectangles": [{"x": 100, "y": 100, "width": 50, "height": 30, "stroke": "#000", "strokeWidth": 2}],
                "circles": [],
                "texts": []
            })
        }
        
        success, response = self.run_test(
            "Save Annotation",
            "POST",
            f"files/{self.file_id}/annotations",
            200,
            data=annotation_data
        )
        return success

    def test_get_annotations(self):
        """Test get annotations"""
        if not self.file_id:
            print("❌ No file ID available")
            return False
            
        success, response = self.run_test(
            "Get Annotations",
            "GET",
            f"files/{self.file_id}/annotations",
            200
        )
        return success

    def test_pricing_ai_gemini(self):
        """Test Pricing AI with Gemini"""
        if not self.file_id:
            print("❌ No file ID available")
            return False
            
        query_data = {
            "file_id": self.file_id,
            "question": "What is the total cost of all items in this file?",
            "provider": "gemini"
        }
        
        success, response = self.run_test(
            "Pricing AI Query (Gemini)",
            "POST",
            "pricing-ai/query",
            200,
            data=query_data
        )
        
        if success and 'response' in response:
            print(f"   AI Response: {response['response'][:100]}...")
        return success

    def test_pricing_ai_openai(self):
        """Test Pricing AI with OpenAI"""
        if not self.file_id:
            print("❌ No file ID available")
            return False
            
        query_data = {
            "file_id": self.file_id,
            "question": "List all unique cabinet codes in this file",
            "provider": "openai"
        }
        
        success, response = self.run_test(
            "Pricing AI Query (OpenAI)",
            "POST",
            "pricing-ai/query",
            200,
            data=query_data
        )
        
        if success and 'response' in response:
            print(f"   AI Response: {response['response'][:100]}...")
        return success

    def test_create_message(self):
        """Test create discussion message"""
        if not self.file_id:
            print("❌ No file ID available")
            return False
            
        message_data = {
            "text": f"Test message created at {datetime.now().isoformat()}"
        }
        
        success, response = self.run_test(
            "Create Message",
            "POST",
            f"files/{self.file_id}/messages",
            200,
            data=message_data
        )
        return success

    def test_get_messages(self):
        """Test get messages"""
        if not self.file_id:
            print("❌ No file ID available")
            return False
            
        success, response = self.run_test(
            "Get Messages",
            "GET",
            f"files/{self.file_id}/messages",
            200
        )
        return success

def main():
    print("🚀 Starting Interior Design AI Suite Backend Tests")
    print("=" * 60)
    
    tester = InteriorDesignAITester()
    
    # Authentication Tests
    print("\n📋 AUTHENTICATION TESTS")
    if not tester.test_auth_signup():
        print("⚠️  Signup failed, trying login...")
        if not tester.test_auth_login():
            print("❌ Both signup and login failed, stopping tests")
            return 1
    
    tester.test_auth_me()
    
    # Project Management Tests
    print("\n📋 PROJECT MANAGEMENT TESTS")
    tester.test_create_project()
    tester.test_get_projects()
    
    # Folder Management Tests
    print("\n📋 FOLDER MANAGEMENT TESTS")
    tester.test_create_folder()
    tester.test_get_folders()
    
    # File Management Tests
    print("\n📋 FILE MANAGEMENT TESTS")
    tester.test_upload_csv_file()
    tester.test_upload_pdf_file()
    tester.test_get_files()
    tester.test_get_file_details()
    
    # Annotation Tests
    print("\n📋 ANNOTATION TESTS")
    tester.test_save_annotation()
    tester.test_get_annotations()
    
    # AI Integration Tests
    print("\n📋 AI INTEGRATION TESTS")
    tester.test_pricing_ai_gemini()
    tester.test_pricing_ai_openai()
    
    # Discussion Tests
    print("\n📋 DISCUSSION TESTS")
    tester.test_create_message()
    tester.test_get_messages()
    
    # Print Results
    print("\n" + "=" * 60)
    print(f"📊 BACKEND TEST RESULTS")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("✅ Backend tests mostly successful!")
        return 0
    else:
        print("❌ Backend has significant issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())