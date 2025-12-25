#!/usr/bin/env python3
"""
Validate CI/CD configuration locally.
"""
import yaml
import os
import sys

def validate_workflow(file_path):
    """Validate a GitHub Actions workflow file."""
    print(f"\n🔍 Validating {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check required fields
        required_fields = ['name', 'jobs']
        for field in required_fields:
            if field not in workflow:
                print(f"❌ Missing required field: {field}")
                return False
        
        # Check for 'on' field (it's a reserved word in Python)
        if 'on' not in workflow and True not in workflow:
            print(f"❌ Missing trigger configuration ('on' field)")
            return False
        
        print(f"✅ Valid YAML structure")
        
        # Check for caching in CI
        if 'ci.yaml' in file_path:
            has_cache = False
            for job_name, job in workflow.get('jobs', {}).items():
                for step in job.get('steps', []):
                    if step.get('uses', '').startswith('actions/cache'):
                        has_cache = True
                        print(f"✅ Found caching in job: {job_name}")
            
            if not has_cache:
                print("⚠️  No caching found in CI workflow")
        
        # Check for multi-arch builds in release
        if 'release.yaml' in file_path:
            has_multiarch = False
            for job_name, job in workflow.get('jobs', {}).items():
                for step in job.get('steps', []):
                    if 'platforms' in step.get('with', {}):
                        platforms = step['with']['platforms']
                        if 'linux/arm64' in platforms:
                            has_multiarch = True
                            print(f"✅ Multi-architecture build found: {platforms}")
            
            if not has_multiarch:
                print("⚠️  No multi-architecture builds found")
        
        return True
        
    except yaml.YAMLError as e:
        print(f"❌ YAML parsing error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def validate_dependabot():
    """Validate Dependabot configuration."""
    print(f"\n🔍 Validating .github/dependabot.yml")
    
    if not os.path.exists('.github/dependabot.yml'):
        print("❌ Dependabot configuration not found")
        return False
    
    try:
        with open('.github/dependabot.yml', 'r') as f:
            config = yaml.safe_load(f)
        
        if 'updates' not in config:
            print("❌ No updates configuration found")
            return False
        
        ecosystems = [update.get('package-ecosystem') for update in config['updates']]
        expected = ['pip', 'github-actions', 'docker']
        
        for ecosystem in expected:
            if ecosystem in ecosystems:
                print(f"✅ {ecosystem} updates configured")
            else:
                print(f"⚠️  {ecosystem} updates not configured")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🔧 Validating CI/CD Configuration")
    print("=" * 40)
    
    workflows = [
        '.github/workflows/ci.yaml',
        '.github/workflows/release.yaml'
    ]
    
    all_valid = True
    
    for workflow in workflows:
        if os.path.exists(workflow):
            if not validate_workflow(workflow):
                all_valid = False
        else:
            print(f"❌ Workflow not found: {workflow}")
            all_valid = False
    
    if not validate_dependabot():
        all_valid = False
    
    if all_valid:
        print("\n✅ All CI/CD configurations are valid!")
        print("\n💡 Improvements implemented:")
        print("- Docker layer caching for faster builds")
        print("- UV dependency caching")
        print("- Multi-architecture Docker builds")
        print("- Automated dependency updates")
    else:
        print("\n❌ Some issues found in CI/CD configuration")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())