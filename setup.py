import io
import os

from setuptools import find_packages, setup

HERE = os.path.abspath(os.path.dirname(__file__))


def load_readme():
    with io.open(os.path.join(HERE, "README.rst"), "rt", encoding="utf8") as f:
        return f.read()


def load_about():
    about = {}
    with io.open(
        os.path.join(HERE, "tutordash", "__about__.py"),
        "rt",
        encoding="utf-8",
    ) as f:
        exec(f.read(), about)  # pylint: disable=exec-used
    return about


ABOUT = load_about()


setup(
    name="tutor-dash",
    version=ABOUT["__version__"],
    url="https://github.com/overhangio/tutor-dash",
    project_urls={
        "Code": "https://github.com/overhangio/tutor-dash",
        "Issue tracker": "https://github.com/overhangio/tutor-dash/issues",
    },
    license="AGPLv3",
    author="Edly",
    author_email="regis.behmo@edly.io",
    description="Awesome administration dashboard and plugin marketplace for Tutor",
    long_description=load_readme(),
    long_description_content_type="text/x-rst",
    packages=find_packages(exclude=["tests*"]),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=[
        "tutor>=18.0.0,<19.0.0",
        "fastapi[standard]",
    ],
    extras_require={
        "dev": [
            "tutor[dev]>=18.0.0,<19.0.0",
        ]
    },
    entry_points={"tutor.plugin.v1": ["dash = tutordash.plugin"]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
