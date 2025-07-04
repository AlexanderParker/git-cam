from setuptools import setup, find_packages

setup(
    name="git-cam",
    version="0.2.1",
    packages=find_packages(),
    scripts=["git-cam"],
    install_requires=["anthropic>=0.39.0", "colorama>=0.4.6", "pathspec>=0.11.2"],
    author="Alex Parker",
    author_email="alexofparker@gmail.com",
    description="An AI-powered Git commit code review and message generator using Claude",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/AlexanderParker/git-cam",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "git-cam=git_cam.main:main",
        ],
    },
)
