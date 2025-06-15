from setuptools import setup, find_packages

setup(
    name='velib-tracker',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Flask',
        'Flask-SQLAlchemy',
        'Flask-CORS',
        'Flask-Migrate',
        'psycopg2-binary',
        'Redis',
        'celery',
        'requests',
        'cloudscraper',
        'APScheduler',
        'geopy',
        'shapely',
        'python-dotenv',
        'gunicorn',
    ],
)