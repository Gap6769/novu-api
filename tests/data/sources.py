SOURCES_DATA = [
    {
        "name": "novelbin",
        "base_url": "https://novelbin.com",
        "content_type": "novel",
        "selectors": {
            "title": "a.novel-title",
            "author": ".author span",
            "description": ".desc-text",
            "cover_image": ".book-img img",
            "status": ".status",
            "tags": ".categories a",
            "chapter_list": ".list-chapter li",
            "chapter_link": "a",
            "chapter_content": "#chr-content",
            "unlock_buttons": ".unlock-buttons",
        },
        "patterns": {
            "chapter_number": "Chapter\\s+(\\d+)",
            "unwanted_text": [
                "Enhance your reading experience by removing ads.*",
                "This material may be protected by copyright.*",
                "Excerpt From.*",
                "Remove Ads From.*",
            ],
        },
        "use_playwright": True,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
        "timeout": 10,
        "max_retries": 3,
        "special_actions": {
            "view_all": {"enabled": False, "selector": None, "wait_after_click": 0, "scroll_after_click": False}
        },
        "is_active": True,
    },
    {
        "name": "pastebin_tbate",
        "base_url": "https://pastebin.com",
        "content_type": "novel",
        "selectors": {},
        "patterns": {
            "chapter_number": "Capítulo\\s+(\\d+)",
            "next_chapter": "Capítulo\\s+\\d+:\\s+(https?://pastebin\\.com/\\w+)",
            "unwanted_text": [
                "Capítulo\\s+\\d+:\\s+\\d{2}/\\d{2}/\\d{4}.*",
                "Please support the translation team.*",
                "Join our Discord for updates.*",
            ],
        },
        "use_playwright": False,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
        "timeout": 10,
        "max_retries": 3,
        "special_actions": {
            "view_all": {"enabled": False, "selector": None, "wait_after_click": 0, "scroll_after_click": False}
        },
        "is_active": True,
    },
    {
        "name": "manhwaweb",
        "base_url": "https://manhwaweb.com",
        "content_type": "manhwa",
        "selectors": {
            "title": "h2.text-left.md\\:text-3xl.xs\\:text-2xl.mb-1.text-xl.font-normal",
            "chapter_list": "div.grid.grid-cols-1.md\\:border.border-y div.flex.p-2.gap-2.border-t",
            "chapter_title": "div.sm\\:text-lg.xs\\:text-base.text-sm",
            "chapter_link": "a.text-gray-500",
            "cover_image": "img.h-full.object-cover.aspect-lezhin",
            "view_all_button": "button.ver_todo",
            "description": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > span",
            "tags": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > div.grid.grid-cols-1 > div > a",
            "author": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > div:nth-child(7) > div.flex.gap-2 > a",
            "status": "#root > div > div:nth-child(1) > div > div.container.mx-auto.max-w-6xl.sm\\:mt-5.mt-2 > div > div > div.sm\\:w-3\\/4.max-w-md.sm\\:max-w-none > div > div:nth-child(5) > div.flex.items-center.gap-2 > div.text-base",
        },
        "patterns": {
            "chapter_number": "Capitulo\\s+(\\d+)",
            "unwanted_text": [
                "Please support the translation team.*",
                "Join our Discord for updates.*",
                "Please read this chapter on our website.*",
            ],
        },
        "use_playwright": True,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
        "timeout": 10,
        "max_retries": 3,
        "special_actions": {
            "view_all": {"enabled": False, "selector": None, "wait_after_click": 0, "scroll_after_click": False}
        },
        "is_active": True,
    },
    {
        "name": "skynovels",
        "base_url": "https://skynovels.net",
        "content_type": "novel",
        "selectors": {
            "title": "h1.skn-novel-presentation-info-title",
            "chapter_list": "div.skn-nvl-info mat-expansion-panel, div.accordion-item",
            "chapter_title": "div.skn-nvl-chp-element-title",
            "chapter_number": "div.skn-nvl-chp-element-chp-number-index",
            "chapter_link": "a.unstyled-a-tag.w-100.skn-link",
            "cover_image": "div.skn-novel-presentation-image img",
            "description": 'meta[name="description"]',
            "tags": "div.skn-nvl-card-genres span.skn-secondary",
            "author": "div.skn-text",
            "status": "div.skn-secondary h4",
            "total_chapters": "div.skn-novel-presentation-info-stats div",
            "chapter_content": "div.skn-chp-chapter-content",
            "content_button": "a.nav-link:has-text('Contenido')",
            "volume_button": "button:has-text('Volumenes'), a:has-text('Volumenes')",
            "volume_panels": "div.skn-nvl-info mat-expansion-panel, div.accordion-item",
            "chapter_links": "a.unstyled-a-tag.w-100.skn-link",
            "expansion_panels": "mat-expansion-panel-header, div.accordion-header button, h2.accordion-header button",
        },
        "patterns": {
            "chapter_number": "Capitulo\\s+(\\d+)",
            "unwanted_text": [
                "Please support the translation team.*",
                "Join our Discord for updates.*",
                "Please read this chapter on our website.*",
                "Visita skynovels.net para.*",
                "Si quieres leer más, visita.*",
                "Todos los derechos reservados.*",
                "Esta historia es propiedad de.*",
                "function\\s*\\(\\s*w\\s*,\\s*q\\s*\\)\\s*\\{\\s*w\\s*\\[\\s*q\\s*\\]\\s*=.*",
                "\\(function\\s*\\(\\s*w\\s*,\\s*q\\s*\\)\\s*\\{\\s*w\\s*\\[\\s*q\\s*\\]\\s*=.*",
                "_mgwidget",
                "_mgq",
                "_mgc\\.load",
            ],
        },
        "use_playwright": True,
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
        "timeout": 10,
        "max_retries": 3,
        "special_actions": {
            "view_all": {"enabled": False, "selector": None, "wait_after_click": 0, "scroll_after_click": False}
        },
        "is_active": True,
    },
]
