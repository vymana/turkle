# Anaconda is used for python package management. Installation: https://docs.anaconda.com/anaconda/install/

conda create -n yscholar python=3.7.6
conda activate yscholar

cd turkle
pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate

python manage.py createsuperuser
#  yscholar/ypassword


python manage.py collectstatic
#run server
python manage.py runserver 0.0.0.0:8000


# Example Proofreading templates
Template: examples/proofreading/proofreading_template.html
Annotation Data: examples/proofreading/proofreading_test.csv