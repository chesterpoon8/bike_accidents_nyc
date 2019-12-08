from app import app
from flask import render_template

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Introduction')

@app.route('/by_month')
def by_month():
    return render_template('by_month.html', title='Accidents by Month')

@app.route('/by_hour')
def by_hour():
    return render_template('by_hour.html', title='Accidents by Hour')

@app.route('/map')
def map():
    return render_template('map.html', title='Map')

@app.route('/data_src')
def data_src():
    return render_template('data_src.html', title='Data Sources')
