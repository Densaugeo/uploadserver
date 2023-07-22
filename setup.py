import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='uploadserver',
    version='5.0.0',
    author='Densaugeo',
    author_email='author@example.com',
    description='Python\'s http.server extended to include a file upload page',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Densaugeo/uploadserver',
    packages=['uploadserver'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
    entry_points = {
        'console_scripts': ['uploadserver=uploadserver:main'],
    }
)
