import logging
import json
import time
import re
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from contact_rules import (
    CONTACT_PATHS, CONTACT_KEYWORDS, FORM_FIELD_INDICATORS,
    NAVIGATION_SELECTORS, SITEMAP_URLS, SEARCH_SETTINGS
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('contact_finder.log'),
        logging.StreamHandler()
    ]
)

class ContactFinder:
    def __init__(self, driver, wait_timeout=None):
        self.driver = driver
        self.wait_timeout = wait_timeout or SEARCH_SETTINGS['wait_timeout']
        self.wait = WebDriverWait(driver, self.wait_timeout)
        self.visited_urls = set()
        self.logger = logging.getLogger(__name__)

    def comprehensive_contact_search(self, base_url=None, max_pages=None):
        max_pages = max_pages or SEARCH_SETTINGS['max_pages']
        
        if base_url is None:
            base_url = self.driver.current_url

        all_contact_data = {
            'contact_links': [],
            'contact_forms': [],
            'email_addresses': [],
            'phone_numbers': [],
            'contact_pages_found': [],
            'search_summary': {},
            'search_metadata': {
                'base_url': base_url,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'pages_searched': []
            }
        }

        self.logger.info(f"Starting comprehensive contact search for {base_url}")

        # Search main page
        self.logger.info("Searching main page")
        main_page_data = self.find_contact_elements()
        self._merge_contact_data(all_contact_data, main_page_data)
        all_contact_data['search_metadata']['pages_searched'].append({
            'url': base_url,
            'contact_found': self._has_contact_info(main_page_data)
        })

        # Expand search if no contact info found on main page
        if not self._has_contact_info(main_page_data):
            self.logger.info("No contact info found on main page. Expanding search")
            
            # Common contact page URLs
            self.logger.info("Trying common contact page URLs")
            contact_urls = self._generate_contact_urls(base_url)
            for url in contact_urls[:max_pages]:
                if len(all_contact_data['contact_pages_found']) >= max_pages:
                    break
                if self._safe_navigate_to_url(url):
                    page_data = self.find_contact_elements()
                    has_contact = self._has_contact_info(page_data)
                    all_contact_data['search_metadata']['pages_searched'].append({
                        'url': url,
                        'contact_found': has_contact
                    })
                    if has_contact:
                        all_contact_data['contact_pages_found'].append(url)
                        self._merge_contact_data(all_contact_data, page_data)

            # Navigation links
            self.logger.info("Searching through navigation links")
            self._search_navigation_links(all_contact_data, base_url, max_pages)

            # Sitemap
            self.logger.info("Checking sitemap")
            self._search_sitemap(all_contact_data, base_url)

        # summary
        all_contact_data['search_summary'] = self._generate_search_summary(all_contact_data)
        
        self.logger.info(f"Search completed. Found {len(all_contact_data['email_addresses'])} emails, "
                        f"{len(all_contact_data['phone_numbers'])} phones, "
                        f"{len(all_contact_data['contact_forms'])} forms")

        return all_contact_data

    def _generate_contact_urls(self, base_url):
        domain = urlparse(base_url).netloc
        urls = []
        for path in CONTACT_PATHS:
            urls.append(f"https://{domain}{path}")
            urls.append(f"https://{domain}{path}.html")
            urls.append(f"https://{domain}{path}.php")
        return urls

    def _safe_navigate_to_url(self, url):
        try:
            if url in self.visited_urls:
                return False
            
            current_url = self.driver.current_url
            self.driver.get(url)
            time.sleep(SEARCH_SETTINGS['page_load_delay'])
            
            if ("404" not in self.driver.title and 
                "not found" not in self.driver.page_source.lower() and
                "error" not in self.driver.page_source.lower()):
                self.visited_urls.add(url)
                return True
            else:
                self.driver.get(current_url)
                return False
                
        except Exception as e:
            self.logger.warning(f"Could not navigate to {url}: {e}")
            return False

    def _search_navigation_links(self, all_contact_data, base_url, max_pages):
        try:
            nav_links = []
            for selector in NAVIGATION_SELECTORS:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    nav_links.extend(elements)
                except:
                    continue

            for link in nav_links:
                if len(all_contact_data['contact_pages_found']) >= max_pages:
                    break
                
                try:
                    href = link.get_attribute('href')
                    link_text = link.text.lower()
                    
                    if (href and base_url in href and 
                        any(keyword in link_text for keyword in CONTACT_KEYWORDS)):
                        
                        if self._safe_navigate_to_url(href):
                            page_data = self.find_contact_elements()
                            has_contact = self._has_contact_info(page_data)
                            all_contact_data['search_metadata']['pages_searched'].append({
                                'url': href,
                                'contact_found': has_contact
                            })
                            if has_contact:
                                all_contact_data['contact_pages_found'].append(href)
                                self._merge_contact_data(all_contact_data, page_data)
                            
                            self.driver.back()
                            time.sleep(1)
                            
                except Exception as e:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error searching navigation links: {e}")

    def _search_sitemap(self, all_contact_data, base_url):
        for sitemap_path in SITEMAP_URLS:
            sitemap_url = f"{base_url}{sitemap_path}"
            try:
                if self._safe_navigate_to_url(sitemap_url):
                    page_source = self.driver.page_source
                    
                    contact_patterns = [
                        r'<loc[^>]*>(.*contact[^<]*)</loc>',
                        r'<url>[^>]*<loc[^>]*>(.*contact[^<]*)</loc>',
                        r'href=[\"\'](.*contact[^\"\']*)[\"\']'
                    ]
                    
                    for pattern in contact_patterns:
                        matches = re.findall(pattern, page_source, re.IGNORECASE)
                        for match in matches:
                            contact_url = match if match.startswith('http') else urljoin(base_url, match)
                            if self._safe_navigate_to_url(contact_url):
                                page_data = self.find_contact_elements()
                                has_contact = self._has_contact_info(page_data)
                                all_contact_data['search_metadata']['pages_searched'].append({
                                    'url': contact_url,
                                    'contact_found': has_contact
                                })
                                if has_contact:
                                    all_contact_data['contact_pages_found'].append(contact_url)
                                    self._merge_contact_data(all_contact_data, page_data)
                                
                                self.driver.back()
                                time.sleep(1)
                    
                    self.driver.get(base_url)
                    break
                    
            except Exception as e:
                self.logger.warning(f"Could not process sitemap {sitemap_url}: {e}")
                continue

    def find_contact_elements(self):
        contact_data = {
            'contact_links': self._find_contact_links(),
            'contact_forms': self._find_contact_forms(),
            'email_addresses': self._extract_emails(),
            'phone_numbers': self._extract_phones()
        }
        return contact_data

    def _find_contact_links(self):
        contact_links = []
        selectors = [
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact')]",
            "//a[contains(translate(@href, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact')]",
            "//a[contains(text(), 'Contact') or contains(text(), 'CONTACT')]",
            "//a[contains(@href, 'contact')]",
            "//a[contains(@class, 'contact')]",
            "//a[contains(@id, 'contact')]",
            "//nav//a[contains(text(), 'Contact')]",
            "//footer//a[contains(text(), 'Contact')]"
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for elem in elements:
                    link_data = {
                        'text': elem.text.strip(),
                        'href': elem.get_attribute('href'),
                        'location': self._get_element_location(elem)
                    }
                    if link_data not in contact_links:
                        contact_links.append(link_data)
            except:
                continue
        
        return contact_links

    def _find_contact_forms(self):
        contact_forms = []
        try:
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            for form in forms:
                if self._is_contact_form(form):
                    form_data = {
                        'fields': self._get_form_fields(form),
                        'action': form.get_attribute('action'),
                        'id': form.get_attribute('id'),
                        'class': form.get_attribute('class')
                    }
                    contact_forms.append(form_data)
        except Exception as e:
            self.logger.warning(f"Error finding contact forms: {e}")
        
        return contact_forms

    def _is_contact_form(self, form):
        form_html = form.get_attribute('outerHTML').lower()
        indicator_count = sum(1 for indicator in CONTACT_KEYWORDS if indicator in form_html)
        field_count = sum(1 for field in FORM_FIELD_INDICATORS if self._form_has_field(form, field))
        return indicator_count >= 2 or field_count >= 2

    def _form_has_field(self, form, field_name):
        field_selectors = [
            f"input[contains(@name, '{field_name}')]",
            f"input[contains(@id, '{field_name}')]",
            f"input[contains(@placeholder, '{field_name}')]",
            f"textarea[contains(@name, '{field_name}')]"
        ]
        
        for selector in field_selectors:
            try:
                if form.find_elements(By.CSS_SELECTOR, selector):
                    return True
            except:
                continue
        return False

    def _get_form_fields(self, form):
        fields = []
        try:
            inputs = form.find_elements(By.TAG_NAME, "input")
            textareas = form.find_elements(By.TAG_NAME, "textarea")
            
            for element in inputs + textareas:
                field_data = {
                    'type': element.get_attribute('type'),
                    'name': element.get_attribute('name'),
                    'placeholder': element.get_attribute('placeholder'),
                    'tag': element.tag_name
                }
                fields.append(field_data)
        except Exception as e:
            self.logger.warning(f"Error getting form fields: {e}")
        
        return fields

    def _extract_emails(self):
        emails = []
        
        # Find mailto links
        try:
            mailto_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'mailto:')]")
            for link in mailto_links:
                href = link.get_attribute('href')
                email = href.replace('mailto:', '').split('?')[0]
                if self._is_valid_email(email):
                    emails.append({
                        'email': email,
                        'source': 'mailto_link',
                        'text': link.text,
                        'location': self._get_element_location(link)
                    })
        except Exception as e:
            self.logger.warning(f"Error extracting mailto emails: {e}")
        
        # Find email addresses in text
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            found_emails = re.findall(email_pattern, page_text)
            
            for email in found_emails:
                if self._is_valid_email(email) and not any(e['email'] == email for e in emails):
                    emails.append({
                        'email': email,
                        'source': 'text_content',
                        'location': 'page_text'
                    })
        except Exception as e:
            self.logger.warning(f"Error extracting text emails: {e}")
        
        return emails

    def _extract_phones(self):
        phones = []
        
        # Find tel links
        try:
            tel_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'tel:')]")
            for link in tel_links:
                href = link.get_attribute('href')
                phone = href.replace('tel:', '')
                phones.append({
                    'phone': phone,
                    'source': 'tel_link',
                    'text': link.text,
                    'location': self._get_element_location(link)
                })
        except Exception as e:
            self.logger.warning(f"Error extracting tel phones: {e}")
        
        # Find phone numbers in text
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            phone_pattern = r'[\+]?[1-9]?[0-9]{7,14}'
            found_phones = re.findall(phone_pattern, page_text)
            
            for phone in found_phones:
                if len(phone) >= 10 and not any(p['phone'] == phone for p in phones):
                    phones.append({
                        'phone': phone,
                        'source': 'text_content',
                        'location': 'page_text'
                    })
        except Exception as e:
            self.logger.warning(f"Error extracting text phones: {e}")
        
        return phones

    def _is_valid_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _get_element_location(self, element):
        try:
            location = element.location
            if location['y'] < 200:
                return 'header'
            elif location['y'] > self.driver.execute_script("return window.innerHeight") - 200:
                return 'footer'
            else:
                return 'body'
        except:
            return 'unknown'

    def _has_contact_info(self, contact_data):
        return (len(contact_data['contact_links']) > 0 or
                len(contact_data['contact_forms']) > 0 or
                len(contact_data['email_addresses']) > 0 or
                len(contact_data['phone_numbers']) > 0)

    def _merge_contact_data(self, all_data, new_data):
        def item_exists(item, existing_list, key_fields):
            for existing in existing_list:
                if all(existing.get(key) == item.get(key) for key in key_fields):
                    return True
            return False
        
        for link in new_data['contact_links']:
            if not item_exists(link, all_data['contact_links'], ['href', 'text']):
                all_data['contact_links'].append(link)
        
        for form in new_data['contact_forms']:
            if not item_exists(form, all_data['contact_forms'], ['action', 'id']):
                all_data['contact_forms'].append(form)
        
        for email in new_data['email_addresses']:
            if not item_exists(email, all_data['email_addresses'], ['email']):
                all_data['email_addresses'].append(email)
        
        for phone in new_data['phone_numbers']:
            if not item_exists(phone, all_data['phone_numbers'], ['phone']):
                all_data['phone_numbers'].append(phone)

    def _generate_search_summary(self, contact_data):
        return {
            'total_pages_searched': len(self.visited_urls),
            'contact_pages_found': len(contact_data['contact_pages_found']),
            'total_contact_links': len(contact_data['contact_links']),
            'total_contact_forms': len(contact_data['contact_forms']),
            'total_emails': len(contact_data['email_addresses']),
            'total_phones': len(contact_data['phone_numbers']),
            'search_successful': self._has_contact_info(contact_data)
        }

    def save_results_to_json(self, contact_data, filename=None):
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            domain = urlparse(contact_data['search_metadata']['base_url']).netloc
            filename = f"contact_results_{domain}_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(contact_data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Results saved to {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Error saving results to JSON: {e}")
            return None