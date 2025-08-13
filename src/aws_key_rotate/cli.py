#!/usr/bin/env python3
"""
AWS IAM Access Key Management Script
This script lists active access keys, creates a new one, updates ~/.aws/credentials,
and deletes the old key that was previously stored in the credentials file.
"""

import boto3
import json
import os
import configparser
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError
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

def get_current_user(sts_client):
    """Get the current IAM user from STS"""
    try:
        response = sts_client.get_caller_identity()
        arn = response['Arn']
        # Extract username from ARN (format: arn:aws:iam::account:user/username)
        username = arn.split('/')[-1]
        return username
    except ClientError as e:
        print_colored(f"Error getting current user: {e}", Colors.RED)
        return None

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

def get_credentials_file_path():
    """Get the path to the AWS credentials file"""
    aws_credentials_file = os.environ.get('AWS_SHARED_CREDENTIALS_FILE')
    if aws_credentials_file:
        return aws_credentials_file
    
    return os.path.expanduser('~/.aws/credentials')

def read_credentials_file(profile='default'):
    """Read the AWS credentials file and return the current access key"""
    credentials_file = get_credentials_file_path()
    
    if not os.path.exists(credentials_file):
        print_colored(f"Credentials file not found at: {credentials_file}", Colors.YELLOW)
        return None, None
    
    try:
        config = configparser.ConfigParser()
        config.read(credentials_file)
        
        if profile not in config:
            print_colored(f"Profile '{profile}' not found in credentials file", Colors.YELLOW)
            return None, None
        
        access_key = config[profile].get('aws_access_key_id')
        secret_key = config[profile].get('aws_secret_access_key')
        
        return access_key, secret_key
        
    except Exception as e:
        print_colored(f"Error reading credentials file: {e}", Colors.RED)
        return None, None

def update_credentials_file(new_access_key_id, new_secret_key, profile='default'):
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
        
        # Update or create the profile section
        if profile not in config:
            config[profile] = {}
        
        config[profile]['aws_access_key_id'] = new_access_key_id
        config[profile]['aws_secret_access_key'] = new_secret_key
        
        # Write the updated configuration
        with open(credentials_file, 'w') as f:
            config.write(f)
        
        print_colored(f"Updated credentials file: {credentials_file}", Colors.GREEN)
        return True
        
    except Exception as e:
        print_colored(f"Error updating credentials file: {e}", Colors.RED)
        return False

def get_profile_from_user():
    """Ask user which profile to use"""
    credentials_file = get_credentials_file_path()
    
    if not os.path.exists(credentials_file):
        return 'default'
    
    try:
        config = configparser.ConfigParser()
        config.read(credentials_file)
        profiles = list(config.sections())
        
        if not profiles:
            return 'default'
        
        if len(profiles) == 1:
            return profiles[0]
        
        print_colored(f"\nFound multiple profiles in {credentials_file}:", Colors.YELLOW)
        for i, profile in enumerate(profiles, 1):
            print(f"{i}. {profile}")
        
        while True:
            try:
                choice = input(f"\nSelect profile to update (1-{len(profiles)}) or press Enter for 'default': ").strip()
                if not choice:
                    return 'default'
                
                choice_num = int(choice)
                if 1 <= choice_num <= len(profiles):
                    return profiles[choice_num - 1]
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number.")
                
    except Exception as e:
        print_colored(f"Error reading profiles: {e}", Colors.RED)
        return 'default'

def main():
    print_colored("AWS IAM Access Key Management with Credentials Update", Colors.GREEN)
    print("====================================================")
    
    try:
        # Initialize AWS clients
        sts_client = boto3.client('sts')
        iam_client = boto3.client('iam')
        
    except NoCredentialsError:
        print_colored("Error: AWS credentials not found. Please configure your credentials.", Colors.RED)
        sys.exit(1)
    
    # Get current user
    print_colored("\nGetting current IAM user...", Colors.YELLOW)
    username = get_current_user(sts_client)
    
    if not username:
        print_colored("Error: Could not determine current IAM user.", Colors.RED)
        sys.exit(1)
    
    print(f"Current IAM User: {username}")
    
    
    # Get the profile to work with
    profile = get_profile_from_user()
    print(f"Working with profile: {profile}")
    
    # Read current credentials from file
    print_colored(f"\nReading current credentials from ~/.aws/credentials [{profile}]...", Colors.YELLOW)
    current_access_key, current_secret_key = read_credentials_file(profile)
    
    if current_access_key:
        print(f"Current access key in credentials file: {current_access_key}")
    else:
        print("No access key found in credentials file")
    
    # List current access keys
    print_colored(f"\nCurrent access keys for user '{username}':", Colors.YELLOW)
    access_keys = list_access_keys(iam_client, username)
    
    if not access_keys:
        print("No access keys found.")
        active_keys = []
    else:
        active_keys = [key for key in access_keys if key['Status'] == 'Active']
        
        print(f"{'Access Key ID':<21} {'Create Date':<25} {'Status'}")
        print("-" * 60)
        for key in access_keys:
            create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S %Z')
            status_color = Colors.GREEN if key['Status'] == 'Active' else Colors.YELLOW
            marker = " <- In credentials file" if key['AccessKeyId'] == current_access_key else ""
            print(f"{key['AccessKeyId']:<21} {create_date:<25} ", end="")
            print_colored(f"{key['Status']}{marker}", status_color)
    
    print(f"\nNumber of active access keys: {len(active_keys)}")
    
    
    # Check if user already has 2 active keys (AWS limit)
    if len(active_keys) >= 2:
        print_colored("Warning: You already have 2 active access keys (AWS limit).", Colors.RED)
        
        # If current key from credentials file exists, offer to delete it
        if current_access_key and any(key['AccessKeyId'] == current_access_key for key in active_keys):
            delete_choice = input(f"\nDelete the current key from credentials file ({current_access_key})? (Y/n): ").strip().lower()
            if delete_choice in ['', 'y', 'yes']:
                key_to_delete = current_access_key
            else:
                # Show other keys for manual selection
                print_colored("\nYour current active access keys:", Colors.YELLOW)
                for i, key in enumerate(active_keys, 1):
                    create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S')
                    print(f"{i}. {key['AccessKeyId']} (Created: {create_date})")
                
                key_to_delete = input("Enter the Access Key ID to delete: ").strip()
        else:
            # Show all keys for manual selection
            print_colored("\nYour current active access keys:", Colors.YELLOW)
            for i, key in enumerate(active_keys, 1):
                create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"{i}. {key['AccessKeyId']} (Created: {create_date})")
            
            key_to_delete = input("Enter the Access Key ID to delete: ").strip()
        
        if key_to_delete:
            print(f"Deleting access key: {key_to_delete}")
            if not delete_access_key(iam_client, username, key_to_delete):
                sys.exit(1)
            print_colored("Access key deleted successfully.", Colors.GREEN)
        else:
            print_colored("No key ID provided. Exiting.", Colors.RED)
            sys.exit(1)
    
    # Create new access key
    print_colored("\nCreating new access key...", Colors.YELLOW)
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
    print_colored(f"\nUpdating ~/.aws/credentials file [{profile}]...", Colors.YELLOW)
    if update_credentials_file(new_key['AccessKeyId'], new_key['SecretAccessKey'], profile):
        print_colored("Credentials file updated successfully!", Colors.GREEN)
        
        # If we had an old key in the credentials file and it wasn't already deleted, delete it now
        if (current_access_key and 
            current_access_key != key_to_delete if 'key_to_delete' in locals() else True and
            any(key['AccessKeyId'] == current_access_key for key in active_keys)):
            
            delete_old = input(f"\nDelete the old access key ({current_access_key}) that was replaced? (Y/n): ").strip().lower()
            if delete_old in ['', 'y', 'yes']:
                print(f"Deleting old access key: {current_access_key}")
                if delete_access_key(iam_client, username, current_access_key):
                    print_colored("Old access key deleted successfully.", Colors.GREEN)
                else:
                    print_colored("Warning: Failed to delete old access key. You may want to delete it manually.", Colors.YELLOW)
    else:
        print_colored("Failed to update credentials file.", Colors.RED)
    
    print_colored("\nIMPORTANT SECURITY NOTES:", Colors.YELLOW)
    print("1. Your credentials file has been updated with the new access key")
    print("2. A backup of your old credentials file was created")
    print("3. Test your applications to ensure they work with the new credentials")
    print("4. The old access key has been deleted from AWS (if requested)")
    
    # Show final list of access keys
    print_colored("\nFinal list of access keys:", Colors.YELLOW)
    updated_keys = list_access_keys(iam_client, username)
    if updated_keys:
        active_updated_keys = [key for key in updated_keys if key['Status'] == 'Active']
        print(f"{'Access Key ID':<21} {'Create Date':<25} {'Status'}")
        print("-" * 60)
        for key in updated_keys:
            create_date = key['CreateDate'].strftime('%Y-%m-%d %H:%M:%S %Z')
            status_color = Colors.GREEN if key['Status'] == 'Active' else Colors.YELLOW
            marker = " <- In credentials file" if key['AccessKeyId'] == new_key['AccessKeyId'] else ""
            print(f"{key['AccessKeyId']:<21} {create_date:<25} ", end="")
            print_colored(f"{key['Status']}{marker}", status_color)

if __name__ == "__main__":
    main()

