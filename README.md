# Event Scheduler
This is a lightweight backend for event scheduler. This can also be used as a module/micro service
- SQLAlchemy
- SQLite
- Flask
- WeatherAPI

# How to Run
## Basic
To run the main code (the backend)
For Windows (default):
```bash
python EventScheduler.py georef-australia-state-suburb.csv au.csv
```
For Linux (default):
```bash
python3 EventScheduler.py georef-australia-state-suburb.csv au.csv
```
## Debugger
The in-built debugger can be optionally activated by setting the parameter in main function
```python
app.run(debug = True)
```


# Project Documentation
## API Documentations
Please refer to the Swagger (hosted on port 8080, by default)

## Special Acknowledgement
The application uses 7Timer [WeatherAPI](https://www.7timer.info/doc.php) to retrieve real-time weather forecast. This is a free API.


