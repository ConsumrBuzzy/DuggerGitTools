"""
Test module for DuggerGitTools cross-project assimilation.
"""

import requests
import click


def fetch_data(url: str) -> dict:
    """Fetch data from a URL."""
    response = requests.get(url)
    return response.json()


@click.command()
@click.option('--url', default='https://api.github.com', help='API endpoint')
def main(url):
    """Test CLI command."""
    data = fetch_data(url)
    click.echo(f"Fetched {len(data)} items")


if __name__ == '__main__':
    main()
