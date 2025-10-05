#!/usr/bin/env python3
"""
Test script for Crew Orchestrator service

Tests basic functionality of the crew-orchestrator API endpoints.
"""

import sys
import json
import asyncio
import httpx

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


class CrewOrchestratorTester:
    def __init__(self, base_url: str = "http://localhost:8084"):
        self.base_url = base_url
        self.tests_passed = 0
        self.tests_failed = 0

    def log_success(self, message: str):
        print(f"{GREEN}✓{RESET} {message}")
        self.tests_passed += 1

    def log_failure(self, message: str):
        print(f"{RED}✗{RESET} {message}")
        self.tests_failed += 1

    def log_info(self, message: str):
        print(f"{BLUE}ℹ{RESET} {message}")

    async def test_root_endpoint(self) -> bool:
        """Test GET / endpoint"""
        print(f"\n{YELLOW}=== Testing Root Endpoint ==={RESET}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/", timeout=5.0)
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_info(f"Response: {json.dumps(data, indent=2)}")
                    
                    # Verify expected fields
                    if data.get("service") == "Crew Orchestrator":
                        self.log_success("Root endpoint returns correct service name")
                    else:
                        self.log_failure("Root endpoint has incorrect service name")
                        return False
                    
                    if "endpoints" in data:
                        self.log_success("Root endpoint includes endpoint information")
                    else:
                        self.log_failure("Root endpoint missing endpoint information")
                        return False
                    
                    return True
                else:
                    self.log_failure(f"Root endpoint returned status {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_failure(f"Root endpoint test failed: {str(e)}")
            return False

    async def test_health_check(self) -> bool:
        """Test GET /healthz endpoint"""
        print(f"\n{YELLOW}=== Testing Health Check Endpoint ==={RESET}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/healthz", timeout=5.0)
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_info(f"Response: {json.dumps(data, indent=2)}")
                    
                    if data.get("ok") is True:
                        self.log_success("Health check endpoint returns ok=true")
                    else:
                        self.log_failure("Health check endpoint returns ok=false")
                        return False
                    
                    if "agents" in data and "tools" in data:
                        self.log_success("Health check includes agent and tool status")
                    else:
                        self.log_failure("Health check missing agent or tool status")
                        return False
                    
                    return True
                else:
                    self.log_failure(f"Health check returned status {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_failure(f"Health check test failed: {str(e)}")
            return False

    async def test_kickoff_valid_task(self) -> bool:
        """Test POST /crew/excel/kickoff with valid task"""
        print(f"\n{YELLOW}=== Testing Kickoff Endpoint (Valid Task) ==={RESET}")
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "goal": "Open Excel and create a new worksheet"
                }
                
                self.log_info(f"Sending payload: {json.dumps(payload, indent=2)}")
                
                response = await client.post(
                    f"{self.base_url}/crew/excel/kickoff",
                    json=payload,
                    timeout=30.0  # Crew execution might take time
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_info(f"Response status: {data.get('status')}")
                    
                    if data.get("status") == "success":
                        self.log_success("Task kickoff successful")
                    else:
                        self.log_failure(f"Task kickoff returned status: {data.get('status')}")
                        return False
                    
                    if "result" in data:
                        self.log_success("Task result included in response")
                        self.log_info(f"Result preview: {str(data['result'])[:100]}...")
                    else:
                        self.log_failure("Task result missing from response")
                        return False
                    
                    return True
                else:
                    self.log_failure(f"Kickoff endpoint returned status {response.status_code}")
                    self.log_info(f"Response: {response.text}")
                    return False
                    
        except Exception as e:
            self.log_failure(f"Kickoff test failed: {str(e)}")
            return False

    async def test_kickoff_invalid_task(self) -> bool:
        """Test POST /crew/excel/kickoff with invalid task"""
        print(f"\n{YELLOW}=== Testing Kickoff Endpoint (Invalid Task) ==={RESET}")
        try:
            async with httpx.AsyncClient() as client:
                # Test with empty goal
                payload = {"goal": ""}
                
                self.log_info("Testing with empty goal (should fail)")
                
                response = await client.post(
                    f"{self.base_url}/crew/excel/kickoff",
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 400 or response.status_code == 422:
                    self.log_success("Empty goal correctly rejected with 400/422 status")
                    return True
                else:
                    self.log_failure(f"Empty goal should return 400/422, got {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_failure(f"Invalid task test failed: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all tests"""
        print(f"\n{'='*60}")
        print(f"Crew Orchestrator Test Suite")
        print(f"Testing: {self.base_url}")
        print(f"{'='*60}")
        
        # Run tests
        await self.test_root_endpoint()
        await self.test_health_check()
        await self.test_kickoff_valid_task()
        await self.test_kickoff_invalid_task()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"Test Results:")
        print(f"  {GREEN}Passed:{RESET} {self.tests_passed}")
        print(f"  {RED}Failed:{RESET} {self.tests_failed}")
        print(f"  {YELLOW}Total:{RESET}  {self.tests_passed + self.tests_failed}")
        print(f"{'='*60}\n")
        
        return self.tests_failed == 0


async def main():
    # Get base URL from command line or use default
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8084"
    
    tester = CrewOrchestratorTester(base_url)
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
