import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from time import sleep

# Function to extract emails from text
def extract_emails_from_text(text):
    return re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)

# Function to extract the main domain from a URL
def get_main_domain(url):
    parsed_url = urlparse(url)
    domain_parts = parsed_url.netloc.split('.')
    # Consider the last two parts of the domain (e.g., spelo.se)
    main_domain = '.'.join(domain_parts[-2:])
    return main_domain

# Function to find all links on the root page
def find_links_on_root_page(url):
    try:
        response = requests.get(url, timeout=10)  # Set timeout for request
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extract all anchor tags with href attribute
        links = [urljoin(url, a['href']) for a in soup.find_all('a', href=True)]
        # Get the main domain of the root URL
        main_domain = get_main_domain(url)
        # Filter links to include only those within the same main domain (including subdomains)
        filtered_links = [link for link in links if get_main_domain(link) == main_domain]
        return filtered_links
    except requests.RequestException as e:
        print(f"Failed to retrieve or parse {url}: {e}")
        return []

# Function to scrape emails from root page and its direct links
def scrape_emails_from_root_and_links(root_url):
    emails_found = set()
    visited_links = set()
    emails_with_links = {}

    # Scrape the root page
    visited_links.add(root_url)
    print(f"Scraping: {root_url}")
    try:
        root_response = requests.get(root_url, timeout=10)
        root_response.raise_for_status()
        emails = extract_emails_from_text(root_response.text)
        emails_found.update(emails)
        if emails:
            emails_with_links[root_url] = set(emails)  # Store as set to ensure uniqueness
    except requests.RequestException as e:
        print(f"Failed to retrieve or parse {root_url}: {e}")

    # Find and scrape all links on the root page
    links = find_links_on_root_page(root_url)
    for link in links:
        if link not in visited_links:
            visited_links.add(link)
            print(f"Scraping: {link}")
            try:
                link_response = requests.get(link, timeout=10)
                link_response.raise_for_status()
                emails = extract_emails_from_text(link_response.text)
                emails_found.update(emails)
                if emails:
                    emails_with_links[link] = set(emails)  # Store as set to ensure uniqueness
            except requests.RequestException as e:
                print(f"Failed to retrieve or parse {link}: {e}")
            sleep(1)  # Sleep to avoid hitting the server too hard

    return visited_links, emails_with_links, emails_found

# Function to update Google Sheet
def update_google_sheet(sheet, row, visited_links, emails_with_links, emails_found):
    # Update the Links Scraped column with each link on a new line
    sheet.update_cell(row, 2, '\n'.join(visited_links))
    
    # Update the Email With Links column with each link and its emails on a new line
    emails_with_links_str = '\n'.join([f'{link} - {", ".join(emails)}' for link, emails in emails_with_links.items()])
    sheet.update_cell(row, 3, emails_with_links_str)
    
    # Update the Emails column with unique emails
    sheet.update_cell(row, 4, ', '.join(emails_found))

# Main function to run the script
def main():
    # Google Sheets API setup
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('C:/Users/user/Downloads/email_scraper_key.json', scope)
    client = gspread.authorize(creds)

    # Open the Google Sheet
    sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1-0l-mE_qoAaanLZzAwmvt9xvTj5P_DPCqnGPfjKH3w0/edit?usp=sharing').sheet1

    # Ask for start and end row numbers
    start_row = int(input("Enter the start row number: "))
    end_row = int(input("Enter the end row number: "))

    # Iterate over the specified rows of the sheet
    for row in range(start_row, end_row + 1):
        domain = sheet.cell(row, 1).value
        if domain:
            print(f"Processing {domain}...")
            root_url = f"http://{domain}" if not domain.startswith('http') else domain
            visited_links, emails_with_links, emails_found = scrape_emails_from_root_and_links(root_url)
            update_google_sheet(sheet, row, visited_links, emails_with_links, emails_found)

if __name__ == "__main__":
    main()
