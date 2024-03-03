# -*- coding: utf-8 -*-
"""
Created on Thu Apr  6 14:21:07 2023

@author: General Ma
"""
from flask import Flask
from flask_restx import Api, Resource, fields, reqparse, abort
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Initialize database
Base = declarative_base()
class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    date = Column(Date)
    description = Column(String)

    def __init__(self, name, date, description):
        self.name = name
        self.date = date
        self.description = description

    def __repr__(self):
        return "<Holiday (id='%s')>" % self.id

engine = create_engine("sqlite:///holidays.db", echo=True, future=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Initialize application
app = Flask(__name__)
api = Api(app, version='1.0', title="Holiday API",
    description='API for managing holiday data',
    default='Method', default_label='all methods are listed here'
)

# Define holiday models
holiday = api.model('Holiday', {
    'name': fields.String(required=True),
    'date': fields.Date(required=True, description='Holiday date in YYYY-MM-DD format'),
    'description': fields.String
})

# Define API routes
@api.route('/holidays')
class Holidays(Resource):
    @api.marshal_list_with(holiday)
    def get(self):
        return session.query(Holiday).all()

    @api.expect(holiday)
    @api.response(201, 'Holiday created successfully', model=holiday)
    def post(self):
        holiday_parser = reqparse.RequestParser()
        holiday_parser.add_argument('name', type=str, help='Name of the holiday', required=True)
        holiday_parser.add_argument('date', type=str, help='Date of the holiday (YYYY-MM-DD)', required=True)
        holiday_parser.add_argument('description', type=str, help='Description of the holiday')

        args = holiday_parser.parse_args()

        # Validate and convert the date format
        try:
            date = datetime.strptime(args['date'], '%Y-%m-%d').date()
        except ValueError:
            abort(400, 'Incorrect date format. Please use YYYY-MM-DD.')

        # Create a new holiday object
        new_holiday = Holiday(
            name=str(args['name']),
            date=date,
            description=str(args['description'])
        )

        session = Session()
        session.add(new_holiday)
        session.commit()

        # Return the new holiday ID, last update time, and a self-reference link
        response = {
            'id': new_holiday.id,
            'name': new_holiday.name,
            '_links': {
                'self': {
                    'href': '/holidays/' + str(new_holiday.id)
                }
            }
        }
        return response, 201

@api.route('/holidays/<int:id>')
class HolidayById(Resource):
    @api.marshal_with(holiday)
    def get(self, id):
        holiday = session.query(Holiday).filter(Holiday.id == id).first()
        if holiday is None:
            abort(404, f'Holiday with id {id} not found')
        return holiday

    @api.response(204, 'Holiday deleted successfully')
    def delete(self, id):
        holiday = session.query(Holiday).filter(Holiday.id == id).first()
        if holiday is None:
            abort(404, f'Holiday with id {id} not found')
            
if __name__ == '__main__':
    #run command:python dbtest.py
    app.run(debug=True,host='127.0.0.1', port=5500)

