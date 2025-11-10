# Common contact page paths to try
CONTACT_PATHS = [
    '/contact', '/contact-us', '/contact.html', '/contact.php',
    '/about', '/about-us', '/about/contact',
    '/info', '/information', '/connect',
    '/support', '/help', '/help/contact',
    '/get-in-touch', '/reach-us', '/find-us',
    '/contacto', '/kontakt', '/contactenos',
    '/feedback', '/report', '/abuse'
]

# Contact-related keywords for identifying contact links
CONTACT_KEYWORDS = [
    'contact', 'about', 'support', 'help', 'info', 'connect',
    'message', 'inquiry', 'question', 'feedback', 'report',
    'abuse', 'copyright', 'privacy', 'terms', 'legal'
]

# Form field indicators for contact forms
FORM_FIELD_INDICATORS = ['name', 'email', 'phone', 'message', 'subject', 'comment', 'inquiry']

# Navigation element selectors for SPAs
NAVIGATION_SELECTORS = [
    "//a",
    "//button",
    "//*[@role='button']",
    "//*[contains(@class, 'button')]",
    "//*[contains(@class, 'link')]",
    "//*[contains(@class, 'menu')]//a",
    "//*[contains(@class, 'nav')]//a",
    "//nav//a",
    "//header//a",
    "//footer//a"
]

# Sitemap URLs to try
SITEMAP_URLS = [
    '/sitemap.xml',
    '/sitemap_index.xml', 
    '/sitemap.php',
    '/sitemap.html',
    '/robots.txt'
]

# SPAs and dynamic content handling
SPA_SETTINGS = {
    'wait_for_dynamic_content': 5,
    'max_scroll_attempts': 3,
    'scroll_pause_time': 2
}

# Search settings
SEARCH_SETTINGS = {
    'max_pages': 15,
    'wait_timeout': 15,
    'page_load_delay': 3,
    'dynamic_content_wait': 5
}