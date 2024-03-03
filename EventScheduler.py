# -*- coding: utf-8 -*-
"""
Created on Tue Apr  2 15:43:09 2023

@author: Nick Ma
"""
from flask import Flask, request, send_file
from flask_restx import Api, Resource, fields, reqparse, abort, Namespace
from datetime import datetime
import requests
import sys
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy import asc, desc
from sqlalchemy.ext.declarative import declarative_base
import matplotlib.pyplot as plt
import io


#Initilize dataset
def load():
    #georef-australia-state-suburb.csv
    georef = sys.argv[1]
    df_georef = pd.read_csv(georef,sep=';')
    #au.csv
    au = sys.argv[2]
    df_au = pd.read_csv(au)
    return df_georef, df_au

df_georef, df_au = load()

#Initilize database
Base = declarative_base()
class EventDB(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    description = Column(String)
    last_updated = Column(DateTime, default=datetime.now())
    street = Column(String)
    suburb = Column(String)
    state = Column(String)
    post_code = Column(String)

    def __init__(self, name, start_time, end_time, description, street, suburb, state, post_code):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.description = description
        self.street = street
        self.suburb = suburb
        self.state = state
        self.post_code = post_code
        
    def __repr__(self):
        return "<Event (id='%s')>" % self.id
    
engine = create_engine("sqlite+pysqlite:///events.db", echo=True, future=True)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
Session = sessionmaker(engine)
    

# Initilize application
app = Flask(__name__)
api = Api(app, version='1.0', title="Nick Ma's MyCalender API",
    description='the best time-management and scheduling calendar service for Australians',
    default='Events', default_label='all events related methods are listed here'
)



# Define event models
location = api.model('Location', {
    'street': fields.String(required=True),
    'suburb': fields.String(required=True),
    'state': fields.String(required=True),
    'post-code': fields.String(required=True)
})

event = api.model('Event', {
    'name': fields.String(required=True),
    'date': fields.Date(required=True),
    'from': fields.DateTime(required=True),
    'to': fields.DateTime(required=True),
    'location': fields.Nested(location),
    'description': fields.String
})

# global variables
events_list = []
DATE_FORMAT_PATTERN = r'^\d{2}-\d{2}-\d{4}$'
TIME_FORMAT_PATTERN = r'^\d{2}:\d{2}:\d{2}$'

# help functions
# help function - map australian state name
def state_name_converter(state_in):
    if state_in.lower() == 'nsw' or state_in.lower() == 'new south wales':
        state_out = 'NSW'
    elif state_in.lower() == 'vic' or state_in.lower() == 'victoria':
        state_out = 'VIC'
    elif state_in.lower() == 'qld' or state_in.lower() == 'queensland':
        state_out = 'QLD'
    elif state_in.lower() == 'sa' or state_in.lower() == 'south australia':
        state_out = 'SA'
    elif state_in.lower() == 'wa' or state_in.lower() == 'western australia':
        state_out = 'WA'
    elif state_in.lower() == 'tas' or state_in.lower() == 'tasmania':
        state_out = 'TAS'
    elif state_in.lower() == 'act' or state_in.lower() == 'australian capital territory':
        state_out = 'ACT'
    elif state_in.lower() == 'nt' or state_in.lower() == 'northern territory':
        state_out = 'NT'
    else:
        raise ValueError('Input is not a state')
    return state_out
        
# help function - used to detect overlapping when creating event
def detect_overlapping(start_time, end_time):
    session = Session()
    overlap = session.query(EventDB).filter(
        ((EventDB.start_time >= start_time) & (EventDB.start_time <= end_time)) |
        ((EventDB.end_time >= start_time) & (EventDB.end_time <= end_time)) |
        (((EventDB.start_time <= start_time) & (EventDB.end_time >= end_time)))
    )
    count = overlap.count()
    return True if count > 0 else False

# help function - used to detect overlapping when updating event
def detect_overlapping_patch(current_event, start_time, end_time):
    is_overlap = False
    session = Session()
    overlap = session.query(EventDB).filter(
        ((EventDB.start_time >= start_time) & (EventDB.start_time <= end_time)) |
        ((EventDB.end_time >= start_time) & (EventDB.end_time <= end_time)) |
        (((EventDB.start_time <= start_time) & (EventDB.end_time >= end_time)))
    )
    count = overlap.count()
    if count > 1 :
        is_overlap =True
    elif count == 1:
        found_event = overlap.first()
        is_overlap = False if found_event.id == current_event.id else True
    else:
        pass
    return is_overlap
    
# help function - find next and prev events
def find_adjacency(current_event):
    session = Session()
    start_time = current_event.start_time
    end_time = current_event.end_time
    previous_event = session.query(EventDB).filter(EventDB.start_time < start_time).order_by(EventDB.start_time.desc()).first()
    next_event = session.query(EventDB).filter(EventDB.start_time > start_time).order_by(EventDB.start_time.asc()).first()
    return previous_event, next_event

# help function - query weather from external API
def weatherAPI(event_id):
    session = Session()
    url = "http://www.7timer.info/bin/api.pl?"
    event = session.query(EventDB).filter_by(id=event_id).first()
    place = df_georef[df_georef['Official Name Suburb'] == event.suburb]
    time = event.start_time.strftime('%Y%m%d%H')
    lon = place['Geo Point'].iloc[0].split(', ')[1]
    lat = place['Geo Point'].iloc[0].split(', ')[0]
    url = url + 'lon=' + str(lon) +'&lat=' + str(lat) + '&product=civil&output=json'
    response = requests.get(url)
    info = {}
    if response.status_code == 200:
        res = response.json()
        target_time = (int(time) - int(res['init']))
        for forecast in res['dataseries']:
            if forecast['timepoint'] > target_time - 3 and forecast['timepoint'] <= target_time:
                info = forecast
    return info
    
# help function - query holiday information from external API
def holidayAPI(event_id):
    session = Session()
    holiday_name = "*Not a holiday*"
    event = session.query(EventDB).filter_by(id=event_id).first()
    year = event.start_time.strftime('%Y')
    date = event.start_time.strftime('%Y-%m-%d')
    state = 'AU-' + event.state
    url = "https://date.nager.at/api/v2/publicholidays/" + year + "/AU"
    response = requests.get(url)
    if response.status_code == 200:
        res = response.json()
        for holiday in res:
            if holiday['date'] == date and (holiday['counties'] == None or state in holiday['counties']):
                holiday_name = holiday['name']
    return holiday_name
    
def check_weekend(date_obj):
    is_weekend = False
    if date_obj.weekday() >= 5:
        is_weekend = True
    
    return is_weekend

# help function -  draw image for summary of event frequency
def image_constructor(total=0, total_current_week=0, total_current_month=0, per_days={}):
    dates = []
    numbers_by_dates = []
    for k,v in per_days.items():
        dates.append(k)
        numbers_by_dates.append(v)
    plt.clf()
    plt.bar(dates, numbers_by_dates,width=0.2)
    
    plt.title('Events numbers')
    plt.xlabel('Date')
    plt.ylabel('Number of events')
    
    yheight = max(numbers_by_dates)+1 if numbers_by_dates != [] else 1
    plt.yticks(range(0, yheight, 1))
    total_text = 'total: '+ str(total)
    
    plt.text(0.1, -0.2, total_text, ha='center', va='center', transform=plt.gca().transAxes)
    plt.text(0.35, -0.2, 'total-current-week: '+str(total_current_week), ha='center', va='center', transform=plt.gca().transAxes)
    plt.text(0.75, -0.2, 'total-current-month: '+str(total_current_month), ha='center', va='center', transform=plt.gca().transAxes)
    plt.subplots_adjust(bottom=0.3)
    
    # convert image into bytes
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    
    return img

# APIs starts here!
@api.route('/events')
class Events(Resource):
# POST an event
    @api.expect(event)
    @api.response(201, 'Event created successfully', model=event)
    @api.response(400, 'Invalid input')
    @api.response(409, 'Events are overlapped')
    def post(self):
        event_parser = reqparse.RequestParser()
        event_parser.add_argument('name', type=str, help='Name of the event', required=True)
        event_parser.add_argument('date', type=str, help='Date of the event (YYYY-MM-DD)', required=True)
        event_parser.add_argument('from', type=str, help='Start time of the event (HH:MM:SS)', required=True)
        event_parser.add_argument('to', type=str, help='End time of the event (HH:MM:SS)', required=True)
        event_parser.add_argument('location', type=dict, help='Location of the event', required=True)
        event_parser.add_argument('description', type=str, help='Description of the event')

        args = event_parser.parse_args()

         # Validate and convert the date and time format
        try:
            start_time = datetime.strptime(args['date'] + ' ' + args['from'], '%Y-%m-%d %H:%M:%S')
            end_time = datetime.strptime(args['date'] + ' ' + args['to'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            abort(400, 'Incorrect date or time format. Please use YYYY-MM-DD and HH:MM:SS, respectively.')
            
        if detect_overlapping(start_time, end_time):
            abort(409, 'Events overlapping detected.')
            
        try:
            state = str(args['location']['state'])
            state = state_name_converter(state)
        except ValueError:
            abort(400, 'Invalid state name, please use Australian states and territories')


        # Create a new event and commit to DB
        new_event = EventDB(
            name=str(args['name']),
            start_time=start_time,
            end_time=end_time,
            description=str(args['description']),
            street=str(args['location']['street']),
            suburb=str(args['location']['suburb']),
            state=state,
            post_code=str(args['location']['post-code']))

        session = Session()
        session.add(new_event)
        session.commit()

        # json response
        response = {
            'id': new_event.id,
            'last-update': str(new_event.last_updated),
            '_links': {
                'self': {
                    'href': '/events/' + str(new_event.id)
                }
            }
        }
        return response, 201
    
# GET a list of events
    @api.response(201, 'Events retrieved successfully')
    @api.response(400, 'Invalid input')
    @api.doc(params={'order': {'description':'ascending or descending order by csv formated value: +name, -name, +id, -id, etc.','required': False}})
    @api.doc(params={'page': {'description':'page to be checked: integer','type': 'int', 'required': False}})
    @api.doc(params={'size': {'description':'events number per page: integer','type': 'int', 'required': False}})
    @api.doc(params={'filter': {'description':'query filter gievn by csv formatted value: e.g. id,name,start_time,description','required': False}})
    def get(self):
        session = Session()
        try:
            order_str = request.args.get('order', '+id').replace(' ', '+')
            order_set = set(order_str.split(','))
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 10))
            filter_str = request.args.get('filter', 'id,name')
            filter_set = set(filter_str.split(','))
        except ValueError:
            abort(400, 'Invalid query, please use order, page, size and filter only.')


        try:
            order_expressions = []
            for order in order_set:
                order_direction = desc if order[0] == '-' else asc
    
                order_field = order[1:]
                if order_field == 'datetime':
                    column = getattr(EventDB, 'start_time', None)
                else:
                    column = getattr(EventDB, order_field, None)
                order_expressions.append(order_direction(column))
                
            if order_expressions == []:
                order_expressions = [asc(EventDB.id)]
     
            events_query = session.query(EventDB).order_by(*order_expressions)
            events = events_query.limit(size).offset((page - 1) * size).all()
            following_items = events_query.offset(page * size).count()
            has_next = True if following_items > 0 else False
    
    
            result = []
            for event in events:
                event_dict = {}
                for condition in filter_set:
                    event_dict[condition] = str(getattr(event, condition))
                result.append(event_dict)
        
        except:
            abort(400, 'Invalid query, inappropriate formatted value or the field requested does not exist.')


        query_string = f"order={order_str}&size={size}&filter={filter_str}"

        self_url = f"/events?{query_string}&page={page}r"
        next_url = f"/events?{query_string}&page={page + 1}" if has_next else "last page reached"

        response = {
            "page": page,
            "page-size": size,
            "events": result,
            "_links": {
                "self": {
                    "href": self_url,
                },
                "next": {
                    "href": next_url
                }
            }
        }
        return response, 200
    

@api.route('/events/<int:event_id>')
class Event(Resource):
# GET an event
    @api.response(200, 'Event retrieved successfully', model=event)
    @api.response(404, 'Event not found')
    def get(self, event_id):
        # Find the event by its ID
        session = Session()
        event = session.query(EventDB).filter_by(id=event_id).first()

        if event is None:
            abort(404, 'Event not found')
        
        try:
            weather_info = weatherAPI(event_id)
            wind_speed = weather_info['wind10m']['speed']
            weather = weather_info['weather']
            humidity = weather_info['rh2m']
            temperature = weather_info['temp2m']
        except:
            index_error_msg = "*not available*"
            wind_speed = index_error_msg
            weather = index_error_msg
            humidity = index_error_msg
            temperature = index_error_msg
            
        holiday_name = holidayAPI(event_id)
        
        
        prev_event, next_event = find_adjacency(event)
        prev_url = '/events/' + str(prev_event.id) if prev_event is not None else 'no existing event'
        next_url = '/events/' + str(next_event.id) if next_event is not None else 'no existing event'

        event_response = {
            'id': event.id,
            'name': event.name,
            'date': str(event.start_time.date()),
            'from': str(event.start_time.time()),
            'to': str(event.end_time.time()),
            'location': {
                'street': event.street,
                'suburb': event.suburb,
                'state': event.state,
                'post-code': event.post_code
                },
            'description': event.description,
            'last-update': str(event.last_updated),
            "_metadata" : {
                  "wind-speed": str(wind_speed) + " KM", 
                  "weather": weather,
                  "humidity": humidity,
                  "temperature": str(temperature) + " C",
                  "holiday": holiday_name,
                  "weekend": check_weekend(event.start_time)
                },
            '_links': {
                'self': {
                    'href': '/events/' + str(event.id)
                },
                'previous': {
                    'href': prev_url
                },
                'next': {
                    'href': next_url
                }
            }
        }

        return event_response, 200
    
# DELETE an event
    @api.response(200, 'Event deleted successfully')
    @api.response(404, 'Event not found')
    def delete(self, event_id):
        # Find the event by ID
        session = Session()
        event = session.query(EventDB).filter_by(id=event_id).first()
        if event is None:
            abort(404, 'Event not found')

        # Remove the event from the list of events
        session.delete(event)
        session.commit()
        delete_response = {
            "message": "Event " + str(event_id) + " has been removed!",
            'id': event_id
        }
        
        return delete_response, 200
    
# PATCH an event
    @api.response(200, 'Event upodated successfully')
    @api.response(400, 'Invalid input')
    @api.response(404, 'Event not found')
    def patch(self, event_id):
        # Find the event by its ID
        session = Session()
        event = session.query(EventDB).filter_by(id=event_id).first()
        if event is None:
            abort(404, 'Event not found')
        
        event_parser = reqparse.RequestParser()
        event_parser.add_argument('name', type=str, help='Name of the event', required=False)
        event_parser.add_argument('date', type=str, help='Date of the event (YYYY-MM-DD)', required=False)
        event_parser.add_argument('from', type=str, help='Start time of the event (HH:MM:SS)', required=False)
        event_parser.add_argument('to', type=str, help='End time of the event (HH:MM:SS)', required=False)
        event_parser.add_argument('location', type=dict, help='Location of the event', required=False)
        event_parser.add_argument('description', type=str, help='Description of the event')

        args = event_parser.parse_args()
        
        # Validate and convert the date and time format
        if args['date'] is None:
            args['date'] = event.start_time.strftime('%Y-%m-%d')
        if args['from'] is not None:
            try:
                start_time = datetime.strptime(args['date'] + ' ' + args['from'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                abort(400, 'Incorrect date or time format. Please use YYYY-MM-DD and HH:MM:SS, respectively.')
        else:
            start_time = None
            
        if args['to'] is not None:
            try:
                end_time = datetime.strptime(args['date'] + ' ' + args['to'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                abort(400, 'Incorrect date or time format. Please use YYYY-MM-DD and HH:MM:SS, respectively.')
        else:
            end_time = None
                
        
        if args['name'] is not None:
            event.name=str(args['name'])
        if start_time is not None:
            event.start_time=start_time
        if end_time is not None:
            event.end_time=end_time
        if args['description'] is not None:
            event.description=str(args['description'])
        if args['location'] is not None:
            event.street=str(args['location']['street'])
            event.suburb=str(args['location']['suburb'])
            event.state=str(args['location']['state'])
            event.post_code=str(args['location']['post-code'])
            
        event.last_updated = datetime.now() 
        
        if event.start_time >= event.end_time:
            abort(400, 'Invalid start or end time.')
        if detect_overlapping_patch(event, event.start_time, event.end_time):
            abort(409, 'Events overlapping detected.')
            
        
        patch_response = {
            'id': event_id,
            'last-update': str(event.last_updated),
            '_links': {
                'self': {
                    'href': '/events/' + str(event.id)
                }
            }  
        }
        session.commit()
        return patch_response, 200
   
# GET event frequency report, either by json or image
@api.route('/events/statistics')
class EventStats(Resource):
    @api.response(200, 'Events statistics successfully')
    @api.response(400, 'Invalid request')
    @api.doc(params={'format': 'The response format can be requested: json, image'})
    def get(self):
        session = Session()
        req_format = request.args.get('format', 'json')
        
        events = session.query(EventDB)
        total = events.count()
        total_current_week = sum(1 for event in events if event.start_time.isocalendar()[1] == datetime.now().isocalendar()[1])
        total_current_month = sum(1 for event in events if event.start_time.month == datetime.now().month)
        per_days = {}
        for event in events:
            date_str = event.start_time.strftime('%Y-%m-%d')
            if date_str not in per_days:
                per_days[date_str] = 1
            else:
                per_days[date_str] += 1
                
        if req_format == 'json':
            response = {
                'total': total,
                'total-current-week': total_current_week,
                'total-current-month': total_current_month,
                'per-days': per_days
            }
            return response, 200
        
        elif req_format == "image":
            image = image_constructor(total, total_current_week, total_current_month, per_days)
            response = send_file(image, mimetype='image/png')
            response.headers.set('content-type' , 'image/png')
            response.status_code = 200     
            
            return response
            
        else:
            abort(400, 'format not supported. Please use json or image.')

# GET weather and geo informtion of the event
# This part is not completely finished, current result is given in json format, due to failure of loading geopands library
@api.route('/weather')
class Weather(Resource):
    @api.doc(tags=['Weather'])
    @api.response(200, 'Weather forecast retrieved successfully')
    @api.response(400, 'Invalid request')
    @api.doc(params={'date': 'The date on which the forecast is demanded: DD-MM-YYYY'})
    def get(self):
        now = datetime.now()
        default_date = now.strftime('%d%m%Y')
        try:
            date_query = request.args.get('date', default_date)
            date_obj = datetime.strptime(date_query, '%d-%m-%Y')
            date = date_obj.strftime('%Y%m%d')
        except:
            abort(400, 'Invalid input, query date format should be  DD-MM-YYYY.')
            
        url = "http://www.7timer.info/bin/api.pl?"
        cities = ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Canberra', 'Adelaide', 'Hobart','Darwin']
        geo_dict = {}
        for city in cities:
            city_info = df_au[df_au['city'] == city]
            lon = city_info.iloc[0,2]
            lat = city_info.iloc[0,1]
            geo_dict.update({city:(float(lon),float(lat))})
        
        
        weather_dict = {}
        for city, lon_lat in geo_dict.items():
            lon = lon_lat[0]
            lat = lon_lat[1]
            url = url + 'lon=' + str(lon) +'&lat=' + str(lat) + '&product=civillight&output=json'
            response = requests.get(url)
            
            weather = "*no forecast made*"
            if response.status_code == 200:
                res = response.json()
                for forecast in res['dataseries']:
                    if str(forecast['date']) == str(date):
                        weather = forecast['weather']
            weather_dict.update({city: {'weather': weather, 'latitude': lat, 'longitude' : lon}})
                
        weather_response = weather_dict
        return weather_response, 200
    
                
        

if __name__ == '__main__':
    #run command:python EventScheduler.py georef-australia-state-suburb.csv au.csv
    #app.run(debug=True)
    app.run(debug=False)
    
    
    


