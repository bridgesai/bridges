#!/usr/bin/env python3
"""
Test Runner for Custom Agent Runner API
Demonstrates the system with a sample problem containing a bug to fix
"""
import os
import sys
import time
import json
import zipfile
import tempfile
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any
import requests
class TestRunner:
    """Test runner for the Custom Agent Runner API"""
    
    def __init__(self, api_url: str = "http://localhost:8888"):
        self.api_url = api_url
        self.test_dir = None
    
    def create_sample_repository(self) -> str:
        """
        Create a sample repository with a bug for the agent to fix
        Returns path to the created repository
        """
        self.test_dir = tempfile.mkdtemp(prefix="test_repo_")
        print(f"Created test repository at: {self.test_dir}")
        
        calculator_py = """
class Calculator:
    '''Simple calculator with basic operations'''
    
    def add(self, a, b):
        '''Add two numbers'''
        return a + b
    
    def subtract(self, a, b):
        '''Subtract b from a'''
        return a - b
    
    def multiply(self, a, b):
        '''Multiply two numbers'''
        return a * b
    
    def divide(self, a, b):
        '''Divide a by b'''
        # BUG: Missing zero division check
        return a / b
    
    def power(self, base, exp):
        '''Calculate base raised to exp'''
        # BUG: Wrong implementation - using multiplication instead of power
        return base * exp  # Should be base ** exp
"""
        
        test_calculator_py = """
import pytest
from calculator import Calculator


class TestCalculator:
    
    def setup_method(self):
        self.calc = Calculator()
    
    def test_addition(self):
        assert self.calc.add(2, 3) == 5
        assert self.calc.add(-1, 1) == 0
        assert self.calc.add(0, 0) == 0
    
    def test_subtraction(self):
        assert self.calc.subtract(5, 3) == 2
        assert self.calc.subtract(0, 5) == -5
        assert self.calc.subtract(-3, -3) == 0
    
    def test_multiplication(self):
        assert self.calc.multiply(3, 4) == 12
        assert self.calc.multiply(-2, 3) == -6
        assert self.calc.multiply(0, 100) == 0
    
    def test_division(self):
        assert self.calc.divide(10, 2) == 5
        assert self.calc.divide(7, 2) == 3.5
        # This test should check for zero division
        with pytest.raises(ZeroDivisionError):
            self.calc.divide(5, 0)
    
    def test_power(self):
        assert self.calc.power(2, 3) == 8  # 2^3 = 8
        assert self.calc.power(5, 2) == 25  # 5^2 = 25
        assert self.calc.power(10, 0) == 1  # Any number^0 = 1
        assert self.calc.power(3, 3) == 27  # 3^3 = 27
"""
        
        readme_md = """# Calculator Module

A simple calculator module with basic arithmetic operations.

## Problem Statement

The calculator module has two bugs that need to be fixed:

1. **Division by Zero**: The `divide` method doesn't handle division by zero properly. It should raise a `ZeroDivisionError` when attempting to divide by zero.

2. **Power Function Bug**: The `power` method incorrectly uses multiplication (*) instead of exponentiation (**). It should calculate base raised to the power of exp.

## Running Tests

To run the tests:
```bash
pytest test_calculator.py -v
```

## Expected Behavior

After fixing the bugs:
- `divide(x, 0)` should raise `ZeroDivisionError`
- `power(2, 3)` should return 8 (not 6)
- `power(5, 2)` should return 25 (not 10)
- All tests should pass
"""
        
        calc_path = Path(self.test_dir) / "calculator.py"
        calc_path.write_text(calculator_py)
        
        test_path = Path(self.test_dir) / "test_calculator.py"
        test_path.write_text(test_calculator_py)
        
        readme_path = Path(self.test_dir) / "README.md"
        readme_path.write_text(readme_md)
        
        requirements = "pytest>=7.0.0\n"
        (Path(self.test_dir) / "requirements.txt").write_text(requirements)
        
        print(f"Created sample files:")
        print(f"  - calculator.py (with bugs)")
        print(f"  - test_calculator.py")
        print(f"  - README.md")
        print(f"  - requirements.txt")
        
        return self.test_dir
    
    def create_zip_file(self, repo_path: str) -> bytes:
        """Create a ZIP file from the repository"""
        zip_buffer = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, repo_path)
                    zipf.write(file_path, arcname)
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.read()
        zip_buffer.close()
        os.unlink(zip_buffer.name)
        
        print(f"Created ZIP file ({len(zip_data)} bytes)")
        return zip_data
    
    def wait_for_api(self, max_attempts: int = 30):
        """Wait for the API to be ready"""
        print("Waiting for API to be ready...")
        for i in range(max_attempts):
            try:
                response = requests.get(f"{self.api_url}/")
                if response.status_code == 200:
                    print("API is ready!")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)
            if i % 5 == 0:
                print(f"  Still waiting... ({i}/{max_attempts})")
        
        print("API did not become ready in time")
        return False
    
    def get_agents(self) -> list:
        """Get list of available agents"""
        response = requests.get(f"{self.api_url}/agents")
        response.raise_for_status()
        return response.json()
    
    def submit_run(self, 
                   agent_id: str,
                   problem_statement: str,
                   inference_url: str,
                   api_key: str,
                   zip_data: bytes) -> str:
        """Submit a run to the API"""
        
        files = {
            'files_zip': ('repository.zip', zip_data, 'application/zip')
        }
        
        data = {
            'agent_id': agent_id,
            'problem_statement': problem_statement,
            'inference_url': inference_url,
            'api_key': api_key
        }
        
        response = requests.post(
            f"{self.api_url}/run",
            data=data,
            files=files
        )
        response.raise_for_status()
        
        result = response.json()
        return result['run_id']
    
    def get_run_status(self, run_id: str) -> Dict[str, Any]:
        """Get the status of a run"""
        response = requests.get(f"{self.api_url}/runs/{run_id}")
        response.raise_for_status()
        print(response.json())
        return response.json()
    
    def wait_for_completion(self, run_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for a run to complete"""
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < timeout:
            status = self.get_run_status(run_id)
            
            if status['status'] != last_status:
                print(f"Run status: {status['status']}")
                last_status = status['status']
            
            if status['status'] in ['completed', 'failed', 'timeout']:
                return status
            
            time.sleep(2)
        
        print(f"Run did not complete within {timeout} seconds")
        return self.get_run_status(run_id)
    
    def validate_fix(self, repo_path: str, patch: str) -> bool:
        """Apply the patch and validate that tests pass"""
        if not patch:
            print("No patch generated")
            return False
        
        print("\n" + "="*60)
        print("APPLYING PATCH")
        print("="*60)
        print(patch[:500] + "..." if len(patch) > 500 else patch)
        
        patch_file = Path(repo_path) / "fix.patch"
        patch_file.write_text(patch)
        
        try:
            result = subprocess.run(
                ["git", "apply", "fix.patch"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Failed to apply patch: {result.stderr}")
                return False
            
            print("Patch applied successfully")
        except Exception as e:
            print(f"Error applying patch: {e}")
            return False
        
        print("\nRunning tests to validate fix...")
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "test_calculator.py", "-v"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            print(result.stdout)
            if result.returncode == 0:
                print("✅ All tests passed! The bugs were fixed successfully.")
                return True
            else:
                print("❌ Some tests still failing:")
                print(result.stdout)
                return False
                
        except Exception as e:
            print(f"Error running tests: {e}")
            return False
    
    def cleanup(self):
        """Clean up test directory"""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            print(f"Cleaned up test directory: {self.test_dir}")
    
    def run_test(self, inference_url: str, api_key: str):
        """Run the complete test"""
        try:
            print("\n" + "="*60)
            print("CUSTOM AGENT RUNNER TEST")
            print("="*60)
            
            if not self.wait_for_api():
                print("ERROR: API is not available")
                return False
            
            print("\n📁 Creating sample repository with bugs...")
            repo_path = self.create_sample_repository()
            
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)
            
            print("\n📦 Creating ZIP file...")
            zip_data = self.create_zip_file(repo_path)
            
            print("\n🤖 Fetching available agents...")
            agents = self.get_agents()
            if not agents:
                print("ERROR: No agents available")
                return False
            
            print(f"Found {len(agents)} agents")
            
            agent = agents[0]
            print(f"Using agent: {agent['version_id']} (score: {agent.get('score', 'N/A')})")
            
            problem_statement = """
Fix the bugs in the calculator.py module:

1. The divide method doesn't handle division by zero. It should raise a ZeroDivisionError when dividing by zero.
2. The power method uses multiplication (*) instead of exponentiation (**). Fix it to correctly calculate base raised to the power of exp.

Make sure all tests in test_calculator.py pass after your fixes.
"""
            
            print("\n🚀 Submitting run...")
            run_id = self.submit_run(
                agent_id=agent['version_id'],
                problem_statement=problem_statement,
                inference_url=inference_url,
                api_key=api_key,
                zip_data=zip_data
            )
            
            print(f"Run submitted: {run_id}")
            
            print("\n⏳ Waiting for agent to complete...")
            result = self.wait_for_completion(run_id, timeout=300)
            
            print("\n" + "="*60)
            print("RESULTS")
            print("="*60)
            print(f"Status: {result['status']}")
            print(f"Duration: {result.get('duration_seconds', 'N/A')} seconds")
            
            if result['status'] == 'completed':
                patch = result.get('patch', '')
                if patch:
                    print(f"Patch generated ({len(patch)} characters)")
                    
                    if self.validate_fix(repo_path, patch):
                        print("\n🎉 SUCCESS! The agent successfully fixed the bugs.")
                        return True
                    else:
                        print("\n⚠️ The agent generated a patch but it didn't fix all issues.")
                else:
                    print("\n⚠️ No patch was generated.")
            else:
                print(f"\n❌ Run failed: {result.get('error', 'Unknown error')}")
                if result.get('logs'):
                    print("\nLogs:")
                    for log in result['logs'][-20:]:
                        print(f"  {log}")
            
            return False
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.cleanup()
def main():
    """Main entry point"""
    api_url = os.getenv("API_URL", "http://localhost:8888")
    inference_url = os.getenv("INFERENCE_URL", "https://api.openai.com/v1/chat/completions")
    api_key = os.getenv("API_KEY", "")
    
    if not api_key:
        print("ERROR: Please set the API_KEY environment variable")
        print("Example: export API_KEY='your-openai-api-key'")
        sys.exit(1)
    
    runner = TestRunner(api_url)
    success = runner.run_test(inference_url, api_key)
    
    sys.exit(0 if success else 1)
if __name__ == "__main__":
    main()