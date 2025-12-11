# /// script
# dependencies = [
#     "colorama",
#     "tabulate",
#     "requests",
# ]
# ///

import requests
import argparse
import sys
import colorama
from tabulate import tabulate
import os
import subprocess

def format_size(KB):
    """Return the given kilobytes as a human-friendly KB, MB, GB, or TB string."""
    if KB < 1:
        return '{0} {1}'.format(KB, 'KB' if 0 == KB > 1 else 'KB')
    elif KB < 1024:
        return '{0:.2f} KB'.format(KB)
    elif 1024 <= KB < 1024 ** 2:
        return '{0:.2f} MB'.format(KB / 1024)
    elif 1024 ** 2 <= KB < 1024 ** 3:
        return '{0:.2f} GB (wow!)'.format(KB / (1024 ** 2))
    elif KB >= 1024 ** 3:
        return '{0:.2f} TB (wow!)'.format(KB / (1024 ** 3))

def check_pat(token, do_download, do_report):
    user_info = get_user_info(token)
    if not user_info:
        return None

    print("\nUser Information:\n")
    username = display_user_info(user_info)
    
    print("\nToken Scopes and Accepted Scopes:\n")
    display_token_scopes(token)
    
    print("\nOrganizations:\n")
    list_organizations(token)
    
    print("\nFinding Repositories:\n")
    repos, total_size = list_repos(token)

    if do_download:
        for repo in repos:
            repo_clone_path = f"https://{username}:{token}@github.com/{repo['full_name']}"
            subprocess.run(["git", "clone", repo_clone_path, os.path.join("Data", "GitHub", repo['full_name'])])
    
    if do_report:
        write_report(username, repos, total_size)

    return user_info.get("login")

def get_user_info(token):
    url = "https://api.github.com/user"
    headers = {
        "Authorization": f"token {token}"
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        print("Invalid token.")
    else:
        print(f"Error: {response.status_code}. {response.text}")
    return None

def display_user_info(user_info):
    table_data = [
        ["Username", user_info.get("login", "Unknown")],
        ["Name", user_info.get("name", "Not provided")],
        ["Bio", user_info.get("bio", "Not provided")],
        ["Public Repos", user_info.get("public_repos", "N/A")],
        ["Followers", user_info.get("followers", "N/A")],
        ["Following", user_info.get("following", "N/A")],
        ["Company", user_info.get("company", "Not provided")],
        ["Location", user_info.get("location", "Not provided")],
        ["Email", user_info.get("email", "Not provided")],
        ["Created At", user_info.get("created_at", "N/A")],
    ]
    print(tabulate(table_data, headers=["Field", "Value"], tablefmt="fancy_grid"))
    return user_info.get("login")

def display_token_scopes(token):
    url = "https://api.github.com/user"
    headers = {
        "Authorization": f"token {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        token_scopes = response.headers.get("X-OAuth-Scopes", "No scopes found")
        accepted_scopes = response.headers.get("X-Accepted-OAuth-Scopes", "No accepted scopes found")
        table_data = [
            ["Token Scopes", token_scopes],
            ["Accepted Scopes", accepted_scopes if accepted_scopes.strip() else "N/A"]
        ]
        print(tabulate(table_data, headers=["Scope Type", "Scopes"], tablefmt="fancy_grid"))

def list_organizations(token):
    url = "https://api.github.com/user/orgs"
    headers = {
        "Authorization": f"token {token}"
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        orgs = response.json()
        table_data = [[org.get("login", "N/A"), org.get("description", "N/A")] for org in orgs]
        if table_data:
            print(tabulate(table_data, headers=["Organization", "Description"], tablefmt="fancy_grid"))
        else:
            print("No organizations found.")
    elif response.status_code == 401:
        print("Invalid token.")
    else:
        print(f"Error: {response.status_code}. {response.text}")

def list_repos(token):
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {token}"
    }
    params = {
        "visibility": "all",
        "affiliation": "owner,collaborator,organization_member",
        "per_page": 100
    }
    repos = []
    total_size = 0
    page = 1
    while True:
        params["page"] = page
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            page_repos = response.json()
            if not page_repos:
                break
            for repo in page_repos:
                total_size += repo['size']
                repos.append(repo)  # Append the entire repo object
            page += 1
        elif response.status_code == 401:
            print("Invalid token.")
            return None, 0
        else:
            print(f"Error: {response.status_code}. {response.text}")
            return None, 0

    return repos, total_size  # Return the complete repo objects and total size

def write_report(username, repos, total_size, url="URL!!CHANGEME", leakix_format=True):
    report_file_path = os.path.join("Data", "GitHub", username + ".md")
    
    with open(report_file_path, 'w') as f:
        f.write(f"""# GitHub credentials and repo contents exposed

## Overview

The URL `{url}` has an exposed git configuration, which allows for access to the token for the `{username}` GitHub account.\n\n""")
        
        f.write(f"## Compromised Repos\n\n")
        if repos:

            headers = ["Repository", "Privacy", "Permissions", "Language", "Size"]
            if not leakix_format:
                f.write(tabulate([[repo['full_name'],
                                "**PRIVATE!**" if repo['private'] else "Public",
                                "**ADMIN!**" if repo['permissions']['admin'] else 
                                "MAINTAINER" if repo['permissions']['maintain'] else 
                                "Push" if repo['permissions']['push'] else 
                                "Pull" if repo['permissions']['pull'] else "None",
                                repo['language'] or "N/A",
                                format_size(repo['size'])] for repo in repos], 
                                headers=headers, 
                                tablefmt="pipe"))
            else:
                i = 1
                for repo in repos:
                    f.write(f"{i}. **Repository:** {repo['full_name']}\n")
                    f.write(f"   - **Privacy:** {'**PRIVATE!**' if repo['private'] else 'Public'}\n")
                    f.write(f"   - **Permissions:** {'Push' if repo['permissions']['push'] else 'Pull' if repo['permissions']['pull'] else 'None'}\n")
                    f.write(f"   - **Language:** {repo['language'] or 'N/A'}\n")
                    f.write(f"   - **Size:** {format_size(repo['size'])}\n\n")
                    i += 1
            f.write("\n\n")
            f.write(f"**Total size of all private repos:** {format_size(total_size)}\n\n")
        else:
            f.write("No compromised repositories found.\n\n")
        
        f.write("""## Leaked Information

- The full contents of all above repos
""")
        
    print(f"Generated report at {report_file_path}.")

def main() -> int:
    parser = argparse.ArgumentParser(description="Enumerates possible attack points with a given GitHub token.")
    parser.add_argument(
        "token", 
        type=str, 
        help="GitHub token to check"
    )
    parser.add_argument(
        "-d",
        "--download",
        action="store_true",
        help="Download all private repos accessible with the token."
    )
    parser.add_argument(
        "-r",
        "--report",
        action="store_true",
        help="Create a report for the token."
    )
    args = parser.parse_args()
    check_pat(args.token, args.download, args.report)
    return 0

if __name__ == "__main__":
    colorama.init(autoreset=True)
    sys.exit(main())
