#!/usr/bin/env python3
"""
AWS IAM Access Key Management Script
This script starts by selecting a profile from ~/.aws/credentials,
uses those credentials for all AWS operations, creates a new access key,
updates the credentials file, and deletes the old key.
"""

import boto3
import json
import os
import configparser
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound
import sys
import shutil

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color

def print_colored(message, color=Colors.NC):
    """Print message with color"""
    print(f"{color}{message}{Colors.NC}")

def get_credentials_file_path():
    """Get the path to the AWS credentials file"""
    aws_credentials_file = os.environ.get('AWS_CREDENTIALS_FILE', '~/.aws/credentials')
    return os.path.expanduser(aws_credentials_file)

def get_available_profiles():
    """Get all available profiles from the credentials file"""
    credentials_file = get_credentials_file_path()
    
    if not os.path.exists(credentials_file):
        print_colored(f"Credentials file not found at: {credentials_file}", Colors.RED)
        return []
    
    try:
        config = configparser.ConfigParser()
        config.read(credentials_file)
        profiles = list(config.sections())
        
        # Add 'default' if it exists in the file (it might not be a section)
        if config.has_option('DEFAULT', 'aws_access_key_id') or 'default' not in profiles:
            # Check if default credentials exist outside of sections
            try:
                test_config = configparser.ConfigParser()
                test_config.read(credentials_file)
                if 'default' not in profiles and os.path.exists(credentials_file):
                    with open(credentials_file, 'r') as f:
                        content = f.read()
                        if 'aws_access_key_id' in content and '[' not in content.split('aws_access_key_id')[0].strip():
                            profiles.insert(0, 'default')
            except:
                pass
        
        return profiles
        
    except Exception as e:
        print_colored(f"Error reading profiles: {e}", Colors.RED)
        return []

def select_profile():
    """Ask user to select a profile to work with"""
    profiles = get_available_profiles()
    
    if not profiles:
        print_colored("No profiles found in credentials file.", Colors.RED)
        create_default = input("Would you like to create a default profile? (y/N): ").strip().lower()
        if create_default in ['y', 'yes']:
            return 'default'
        else:
            sys.exit(1)
    
    if len(profiles) == 1:
        profile = profiles[0]
        use_only = input(f"Found profile '{profile}'. Use this profile? (Y/n): ").strip().lower()
        if use_only in ['', 'y', 'yes']:
            return profile
    
    print_colored(f"\nAvailable profiles in {get_credentials_file_path()}:", Colors.YELLOW)
    for i, profile in enumerate(profiles, 1):
        print(f"{i}. {profile}")
    
    while True:
        try:
            choice = input(f"\nSelect profile to work with (1-{len(profiles)}): ").strip()
            choice_num = int(choice)
            if 1 <= choice_num <= len(profiles):
                return profiles[choice_num - 1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def read_profile_credentials(profile):
    """Read credentials for a specific profile"""
    credentials_file = get_credentials_file_path()
    
    if not os.path.exists(credentials_file):
        return None, None
    
    try:
        config = configparser.ConfigParser()
        config.read(credentials_file)
        
        section = profile if profile in config else 'DEFAULT'
        
        if section not in config:
            print_colored(f"Profile '{profile}' not found in credentials file", Colors.RED)
            return None, None
        
        access_key = config[section].get('aws_access_key_id')
        secret_key = config[section].get('aws_secret_access_key')
        
        return access_key, secret_key
        
    except Exception as e:
        print_colored(f"Error reading credentials for profile '{profile}': {e}", Colors.RED)
        return None, None

def create_boto3_session(profile):
    """Create a boto3 session using the specified profile"""
    try:
        # Try to create session with the profile
        session = boto3.Session(profile_name=profile)
        
        # Test the credentials by making a simple call
        sts_client = session.client('sts')
        sts_client.get_caller_identity()
        
        return session
        
    except ProfileNotFound:
        print_colored(f"Profile '{profile}' not found in AWS configuration.", Colors.RED)
        return None
    except NoCredentialsError:
        print_colored(f"No credentials found for profile '{profile}'.", Colors.RED)
        return None
    except ClientError as e:
        print_colored(f"Error authenticating with profile '{profile}': {e}", Colors.RED)
        return None

def get_current_user(sts_client):
    """Get the current IAM user from STS"""
    try:
        response = sts_client.get_caller_identity()
        arn = response['Arn']
        # Extract username from ARN (format: arn:aws:iam::account:user/username)
        username = arn.split('/')[-1]
        account_id = response['Account']
        return username, account_id
    except ClientError as e:
        print_colored(f"Error getting current user: {e}", Colors.RED)
        return None, None

def list_access_keys(iam_client, username):
    """List all access keys for a user"""
    try:
        response = iam_client.list_access_keys(UserName=username)
        return response['AccessKeyMetadata']
    except ClientError as e:
        print_colored(f"Error listing access keys: {e}", Colors.RED)
        return []

def delete_access_key(iam_client, username, access_key_id):
    """Delete an access key"""
    try:
        iam_client.delete_access_key(UserName=username, AccessKeyId=access_key_id)
        return True
    except ClientError as e:
        print_colored(f"Error deleting access key: {e}", Colors.RED)
        return False

def create_access_key(iam_client, username):
    """Create a new access key"""
    try:
        response = iam_client.create_access_key(UserName=username)
        return response['AccessKey']
    except ClientError as e:
        print_colored(f"Error creating access key: {e}", Colors.RED)
        return None

def update_credentials_file(profile, new_access_key_id, new_secret_key):
    """Update the AWS credentials file with new credentials"""
    credentials_file = get_credentials_file_path()
    
    # Create backup
    if os.path.exists(credentials_file):
        backup_file = f"{credentials_file}.backup"
        shutil.copy2(credentials_file, backup_file)
        print_colored(f"Created backup: {backup_file}", Colors.YELLOW)
    
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(credentials_file), exist_ok=True)
        
        config = configparser.ConfigParser()
        if os.path.exists(credentials_file):
            config.read(credentials_file)
        
        # Handle default profile specially
        section = profile if profile != 'default' else 'default'
        
        # Update or create the profile section
        if section not in config:
            config[section] = {}
        
        config[section]['aws_access_key_id'] = new_access_key_id
        config[section]['aws_secret_access_key'] = new_secret_key
        
        # Write the updated configuration
        with open(credentials_file, 'w') as f:
            config.write(f)
        
        print_colored(f"Updated credentials file: {credentials_file} [profile: {profile}]", Colors.GREEN)
        return True
        
    except Exception as e:
        print_colored(f"Error updating credentials file: {e}", Colors.RED)
        return False

def main():
    print_colored("AWS IAM Access Key Rotation", Colors.GREEN)
    print        ("===========================")
    
    # Step 1: Select profile first
    print_colored("\nStep 1: Select AWS Profile", Colors.YELLOW)
    profile = select_profile()
    print(f"Selected profile: {profile}")
    
    # Step 2: Create boto3 session with selected profile
    print_colored(f"\nStep 2: Initialize AWS session with profile '{profile}'", Colors.YELLOW)
    session = create_boto3_session(profile)
    
    if not session:
        print_colored("Failed to create AWS session. Please check your credentials.", Colors.RED)
        sys.exit(1)
    
    # Create clients using the session
    sts_client = session.client('sts')
    iam_client = session.client('iam')
    
    # Get current user info
    print_colored("\nStep 3: Verify current user identity", Colors.YELLOW)
    username, account_id = get_current_user(sts_client)
    
    if not username:
        print_colored("Error: Could not determine current IAM user.", Colors.RED)
        sys.exit(1)
    
    print(f"Current IAM User: {username}")
    print(f"AWS Account ID: {account_id}")
    
    # Read current credentials from file for this profile
    print_colored(f"\nStep 4: Read current credentials for profile '{profile}'", Colors.YELLOW)
    current_access_key, current_secret_key = read_profile_credentials(profile)
    
    if current_access_key:
        print(f"Current access key in profile '{profile}': {current_access_key}")
    else:
        print(f"No access key found for profile '{profile}' in credentials file")
    
    # List current access keys
    print_colored(f"\nStep 5: List current access keys for user '{username}'", Colors.YELLOW)
    access_keys = list_access_keys(iam_client, username)
    
    if not access_keys:
        print("No access keys found.")
        active_keys = []
    else:
        active_keys = [key for key in access_keys if key['Status'] == 'Active']
        
        print(f"{'Access Key ID':<21} {'Create Date':<25} {'Status'}")
        print("-" * 75)
        for key in access_keys:
            create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S %Z')
            status_color = Colors.GREEN if key['Status'] == 'Active' else Colors.YELLOW
            marker = f" <- Used by profile '{profile}'" if key['AccessKeyId'] == current_access_key else ""
            print(f"{key['AccessKeyId']:<21} {create_date:<25} ", end="")
            print_colored(f"{key['Status']}{marker}", status_color)
    
    print(f"\nTotal access keys: {len(access_keys)} (Active: {len(active_keys)}, Inactive: {len(access_keys) - len(active_keys)})")
    
    # Check if user already has 2 access keys total (AWS limit)
    if len(access_keys) >= 2:
        print_colored("\nStep 6: Handle AWS access key limit (2 keys maximum)", Colors.YELLOW)
        print_colored("Warning: You already have 2 access keys (AWS limit of 2 total keys).", Colors.RED)
        
        # Smart key selection: prioritize inactive keys, then oldest
        def get_recommended_key_to_delete():
            # First, check for inactive keys
            inactive_keys = [key for key in access_keys if key['Status'] == 'Inactive']
            if inactive_keys:
                # Return the oldest inactive key
                return min(inactive_keys, key=lambda k: k['CreateDate'])
            
            # If no inactive keys, return the oldest active key
            active_keys_list = [key for key in access_keys if key['Status'] == 'Active']
            if active_keys_list:
                return min(active_keys_list, key=lambda k: k['CreateDate'])
            
            # Fallback to first key (shouldn't happen)
            return access_keys[0] if access_keys else None
        
        recommended_key = get_recommended_key_to_delete()
        
        if recommended_key:
            create_date = recommended_key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S')
            reason = "inactive" if recommended_key['Status'] == 'Inactive' else "oldest"
            
            print_colored(f"\nRecommended key to delete ({reason}):", Colors.YELLOW)
            print(f"  {recommended_key['AccessKeyId']} ({recommended_key['Status']}) - Created: {create_date}")
            
            # If the recommended key is the current profile key, mention it
            profile_key_note = ""
            if recommended_key['AccessKeyId'] == current_access_key:
                profile_key_note = f" (currently used by profile '{profile}')"
            
            delete_choice = input(f"\nDelete recommended key {recommended_key['AccessKeyId']}{profile_key_note}? (Y/n): ").strip().lower()
            
            if delete_choice in ['', 'y', 'yes']:
                key_to_delete = recommended_key['AccessKeyId']
            else:
                # Show all keys for manual selection
                print_colored("\nAll your access keys:", Colors.YELLOW)
                for i, key in enumerate(access_keys, 1):
                    create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S')
                    status_indicator = f"({key['Status']})"
                    profile_note = f" <- Profile '{profile}'" if key['AccessKeyId'] == current_access_key else ""
                    recommended_note = " [RECOMMENDED]" if key['AccessKeyId'] == recommended_key['AccessKeyId'] else ""
                    print(f"{i}. {key['AccessKeyId']} {status_indicator} (Created: {create_date}){profile_note}{recommended_note}")
                
                key_to_delete = input("Enter the Access Key ID to delete: ").strip()
        else:
            # Fallback - shouldn't happen but handle gracefully
            print_colored("\nYour current access keys:", Colors.YELLOW)
            for i, key in enumerate(access_keys, 1):
                create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S')
                status_indicator = f"({key['Status']})"
                print(f"{i}. {key['AccessKeyId']} {status_indicator} (Created: {create_date})")
            
            key_to_delete = input("Enter the Access Key ID to delete: ").strip()
        
        if key_to_delete:
            print(f"Deleting access key: {key_to_delete}")
            if not delete_access_key(iam_client, username, key_to_delete):
                sys.exit(1)
            print_colored("Access key deleted successfully.", Colors.GREEN)
        else:
            print_colored("No key ID provided. Exiting.", Colors.RED)
            sys.exit(1)
    else:
        print_colored("\nStep 6: Access key limit check - OK", Colors.YELLOW)
        print("You have room for additional access keys.")
    
    # Create new access key
    print_colored("\nStep 7: Create new access key", Colors.YELLOW)
    new_key = create_access_key(iam_client, username)
    
    if not new_key:
        print_colored("Failed to create new access key.", Colors.RED)
        sys.exit(1)
    
    print_colored("\nNew access key created successfully!", Colors.GREEN)
    print("==================================")
    print(f"Access Key ID: {new_key['AccessKeyId']}")
    print(f"Secret Access Key: {new_key['SecretAccessKey']}")
    print("==================================")
    
    # Update credentials file
    print_colored(f"\nStep 8: Update credentials file for profile '{profile}'", Colors.YELLOW)
    if update_credentials_file(profile, new_key['AccessKeyId'], new_key['SecretAccessKey']):
        print_colored("Credentials file updated successfully!", Colors.GREEN)
        
        # If we had an old key in the profile and it wasn't already deleted, delete it now
        if (current_access_key and 
            current_access_key != (key_to_delete if 'key_to_delete' in locals() else None) and
            any(key['AccessKeyId'] == current_access_key for key in list_access_keys(iam_client, username))):
            
            print_colored(f"\nStep 9: Clean up old access key", Colors.YELLOW)
            delete_old = input(f"Delete the previous current access key ({current_access_key})? (Y/n): ").strip().lower()
            if delete_old in ['', 'y', 'yes']:
                print(f"Deleting old access key: {current_access_key}")
                if delete_access_key(iam_client, username, current_access_key):
                    print_colored("Old access key deleted successfully.", Colors.GREEN)
                else:
                    print_colored("Warning: Failed to delete old access key. You may want to delete it manually.", Colors.YELLOW)
            else:
                print_colored("Old access key retained (not deleted).", Colors.YELLOW)
        else:
            print_colored("\nStep 9: Clean up - No additional cleanup needed", Colors.YELLOW)
    else:
        print_colored("Failed to update credentials file.", Colors.RED)
        sys.exit(1)
    
    print_colored("\nProcess completed successfully!", Colors.GREEN)
    print_colored("\nIMPORTANT NOTES:", Colors.YELLOW)
    print(f"1. Profile '{profile}' has been updated with the new access key")
    print("2. A backup of your old credentials file was created")
    print("3. Test your applications to ensure they work with the new credentials")
    print("4. All AWS operations used the selected profile's credentials")
    
    # Show final list of access keys
    print_colored(f"\nFinal status for user '{username}':", Colors.YELLOW)
    updated_keys = list_access_keys(iam_client, username)
    if updated_keys:
        print(f"{'Access Key ID':<21} {'Create Date':<25} {'Status'}")
        print("-" * 75)
        for key in updated_keys:
            create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S %Z')
            status_color = Colors.GREEN if key['Status'] == 'Active' else Colors.YELLOW
            marker = f" <- Profile '{profile}'" if key['AccessKeyId'] == new_key['AccessKeyId'] else ""
            print(f"{key['AccessKeyId']:<21} {create_date:<25} ", end="")
            print_colored(f"{key['Status']}{marker}", status_color)


if __name__ == "__main__":
    main()