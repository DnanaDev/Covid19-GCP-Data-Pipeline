from setuptools import setup


setup(
    name='Data_Pipeline',
    version='0.1',
    description='Covid19-India Data Pipeline',
      author='Anand',
      author_email='anand.work@gmail.com',
    packages=['Data_Pipeline',],
    license='MIT',
    long_description=open('README.txt').read(),
    python_requires = '>=3.6.4',
    install_requires = ['pandas'],
)