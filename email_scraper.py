import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from time import sleep

# User-Agent to mimic real browser requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Function to extract emails from text
def extract_emails_from_text(text):
    return set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))

# Function to extract the main domain from a URL
def get_main_domain(url):
    parsed_url = urlparse(url)
    domain_parts = parsed_url.netloc.split('.')
    return '.'.join(domain_parts[-2:])  # Example: example.com

# Function to find valid links on the root page, excluding images and external domains
def find_links_on_root_page(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        # Ensure response is HTML
        if 'text/html' not in response.headers.get('Content-Type', ''):
            print(f"Skipping non-HTML content: {url}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        main_domain = get_main_domain(url)

        # Extract and filter links
        links = [
            urljoin(url, a['href'])
            for a in soup.find_all('a', href=True)
        ]
        filtered_links = [
            link for link in links
            if get_main_domain(link) == main_domain and not re.search(r'\.(png|jpg|jpeg|gif|svg|webp|bmp|ico|pdf|mp4|mp3)$', link, re.IGNORECASE)
        ]
        return filtered_links

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

# Function to scrape emails from a given page
def scrape_emails_from_url(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        # Ensure response is HTML
        if 'text/html' not in response.headers.get('Content-Type', ''):
            print(f"Skipping non-HTML content: {url}")
            return set()

        return extract_emails_from_text(response.text)

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return set()

# Function to scrape emails from root page and its internal links
def scrape_emails_from_root_and_links(root_url):
    emails_found = set()
    visited_links = set()
    emails_with_links = {}

    print(f"Scraping root: {root_url}")
    visited_links.add(root_url)

    # Scrape root page
    emails = scrape_emails_from_url(root_url)
    emails_found.update(emails)
    if emails:
        emails_with_links[root_url] = emails

    # Scrape internal links
    links = find_links_on_root_page(root_url)
    for link in links:
        if link not in visited_links:
            print(f"Scraping link: {link}")
            visited_links.add(link)

            emails = scrape_emails_from_url(link)
            emails_found.update(emails)
            if emails:
                emails_with_links[link] = emails

            sleep(1)  # Avoid overloading the server

    return visited_links, emails_with_links, emails_found

# Function to update Google Sheet
def update_google_sheet(sheet, row, visited_links, emails_with_links, emails_found):
    try:
        # Update the "Links Scraped" column
        sheet.update_cell(row, 2, '\n'.join(visited_links))

        # Update the "Emails With Links" column
        emails_with_links_str = '\n'.join(
            [f'{link} - {", ".join(emails)}' for link, emails in emails_with_links.items()]
        )
        sheet.update_cell(row, 3, emails_with_links_str)

        # Update the "Emails" column
        sheet.update_cell(row, 4, ', '.join(emails_found))

    except Exception as e:
        print(f"Error updating Google Sheet: {e}")

# Main function to run the script
def main():
    # Google Sheets API setup
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Load service account credentials from environment variable
    key_data = os.getenv("EMAIL_SCRAPER_KEY")
    if not key_data:
        raise Exception("EMAIL_SCRAPER_KEY environment variable not found!")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(key_data), scope)
    client = gspread.authorize(creds)

    # Open the Google Sheet
    sheet_url = "https://docs.google.com/spreadsheets/d/1-0l-mE_qoAaanLZzAwmvt9xvTj5P_DPCqnGPfjKH3w0/edit?usp=sharing"
    sheet = client.open_by_url(sheet_url).sheet1

    # Get number of rows with data in column A
    rows_with_data = len(sheet.col_values(1))

    # Process each domain from the Google Sheet
    for row in range(2, rows_with_data + 1):
        domain = sheet.cell(row, 1).value
        if domain:
            print(f"Processing {domain}...")
            root_url = f"http://{domain}" if not domain.startswith("http") else domain
            visited_links, emails_with_links, emails_found = scrape_emails_from_root_and_links(root_url)
            update_google_sheet(sheet, row, visited_links, emails_with_links, emails_found)

if __name__ == "__main__":
    main()
