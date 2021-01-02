import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='uploadserver',
    version='0.2.2',
    author='Densaugeo',
    author_email='author@example.com',
    description='Python\'s http.server extended to include a file upload page',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Densaugeo/uploadserver',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
