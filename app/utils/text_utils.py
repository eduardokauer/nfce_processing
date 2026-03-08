from bs4 import BeautifulSoup


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
