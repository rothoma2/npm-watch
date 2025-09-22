import os
import logging
import configparser
import requests
from pprint import pprint
from dataclasses import dataclass

@dataclass
class NpmPackageInfo:
    normalized_name: str
    protocol_type: str
    normalized_version: str
    published_date: str
    is_latest: bool
    scope: str = ''

@dataclass
class FeedInfo:
    project_id: str
    feed_id: str
    feed_name: str

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


logger = setup_logger()  # Global logger
pat_token = None  # Global PAT token
project_id = None  # Global variable to store project id


def read_config(config_path):

    logger.debug(f"Reading config file. ")
    config = configparser.ConfigParser()
    config.read(config_path)

    try:
        org_names_raw = config['azure'].get('organization_names', '')
        org_names = [
            name.strip().strip('"')
            for name in org_names_raw.split(',')
            if name.strip()
        ]
        if not org_names:
            raise ValueError(
                "No organization names found in [azure] section of config file."
            )
    except KeyError:
        raise ValueError(
            "Missing 'organization_names' in [azure] section of config file."
        )
    return org_names

def get_pat_token():
    global pat_token
    logger.info("Getting PAT token from environment.")
    pat_token = os.getenv('AZDO_PAT')
    if not pat_token:
        raise EnvironmentError(
            "AZURE_DEVOPS_PAT environment variable not set."
        )
    return pat_token

def get_feeds_json(organization):
    url = f"https://feeds.dev.azure.com/{organization}/_apis/packaging/feeds?api-version=6.0-preview.1"
    logger.debug(f"Fetching feeds from URL: {url}")
    response = requests.get(url, auth=("", pat_token))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch feeds for {organization}: {response.text}")
    return response.json()

def extract_feed_infos(feeds_json):
    feeds = feeds_json.get("value", [])
    feed_infos = []
    for feed in feeds:
        project_id = feed.get("project", {}).get("id", "")
        feed_id = feed.get("id", "")
        feed_name = feed.get("name", "")
        feed_infos.append(FeedInfo(project_id, feed_id, feed_name))
    return feed_infos

def list_npm_packages(organization, feed_info):
    url = (
        f"https://feeds.dev.azure.com/"
        f"/{organization}/{feed_info.project_id}/_apis/Packaging/Feeds/"
        f"{feed_info.feed_id}/Packages?protocolType=npm&api-version=6.0-preview.1"
    )
    logger.debug(url)
    response = requests.get(url, auth=("", pat_token))
    if response.status_code != 200:
        raise Exception(
            f"Failed to list npm packages: {response.text}"
        )
    packages_json = response.json().get("value", [])
    packages = [parse_npm_package(pkg) for pkg in packages_json]
    return packages

def extract_project_id(feed_yaml):
    global project_id
    feeds = feed_yaml.get('value', [])
    if not feeds:
        raise ValueError("No feeds found in YAML data.")

    project = feeds[0].get('project', {})
    project_id = project.get('id')
    if not project_id:
        raise ValueError("Project ID not found in feed data.")
    return project_id

def parse_npm_package(package_json):

    normalized_name = package_json.get('normalizedName', '')
    protocol_type = package_json.get('protocolType', '')
    if normalized_name.startswith('@') and '/' in normalized_name:
        scope = normalized_name.split('/')[0][1:]
    else:
        scope = ''
    latest_version = None
    for v in package_json.get('versions', []):
        if v.get('isLatest'):
            latest_version = v
            break
    if latest_version:
        normalized_version = latest_version.get('normalizedVersion', '')
        published_date = latest_version.get('publishDate', '')
        is_latest = latest_version.get('isLatest', False)
    else:
        normalized_version = ''
        published_date = ''
        is_latest = False

    return NpmPackageInfo(
        normalized_name=normalized_name,
        protocol_type=protocol_type,
        normalized_version=normalized_version,
        published_date=published_date,
        is_latest=is_latest,
        scope=scope
    )

def main():
    config_path = 'config.ini'
    packages = []
    try:
        org_names = read_config(config_path)
        get_pat_token()

        for org in org_names:

            logger.info(f"Using Azure DevOps organization: {org}")
            feeds_json = get_feeds_json(org)
            feed_infos = extract_feed_infos(feeds_json)
            logger.info(f"Number of Feeds Retrieved: {len(feed_infos)}")
            logger.debug(f"Feed Infos: {[f'{fi.feed_name} ({fi.feed_id}, {fi.project_id})' for fi in feed_infos]}")

            if feed_infos:
                feed = feed_infos[0]
                logger.info(f"Listing NPM packages for feed: {feed.feed_name} ({feed.feed_id})")
                packages = list_npm_packages(org, feed)
                logger.info(f"NPM packages in feed (count: {len(packages)}):")

        pprint(packages[0])
#            for pkg in packages:
#                print(pkg.normalized_name)

    except Exception as e:
        logger.error(f"Error: {e}")
        return
    # ... further logic ...

if __name__ == "__main__":
    main()
