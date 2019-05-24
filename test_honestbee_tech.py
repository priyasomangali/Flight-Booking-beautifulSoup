from datetime import datetime, timedelta
import datetime
from dateutil.rrule import rrule, MONTHLY, DAILY
import requests
from bs4 import BeautifulSoup

import pandas as pd
from math import pi
from bokeh.io import output_file
from bokeh.models import DatetimeTickFormatter
from bokeh.plotting import figure, show


class UnAcceptedValueError(Exception):
    def __init__(self, data):
        self.data = data

    def __str__(self):
        return repr(self.data)


class TestTigerAir:
    @classmethod
    def setup_class(cls):
        cls.url = "https://booking.tigerair.com.au/TigerAirIBE/Booking/Search"
        cls.query_period_lowest_fares = {}
        cls.header_date_fare = {}
        cls.query_price_list = []
        cls.query_date_list = []
        cls.list_last_year = []
        cls.session = requests.Session()
        cls.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36'})

        cls.tokenRequest = cls.session.get('https://booking.tigerair.com.au/TigerAirIBE/Booking/Search')
        cls.soup = BeautifulSoup(cls.tokenRequest.text, 'lxml')
        cls.csrf = cls.soup.find('input', {'name': '__RequestVerificationToken'}).get('value')
        cls.sessionCookies = cls.tokenRequest.cookies

    def clear_class_objects(self):
        self.query_period_lowest_fares.clear()
        self.header_date_fare.clear()
        self.query_date_list = []
        self.query_price_list = []
        self.query_date_year = []
        self.list_last_year = []

    def get_date_difference(self, d1, d2=None):
        date_difference = {}
        date1 = datetime.datetime.strptime(str(d1), '%Y-%m-%d')
        date2 = datetime.datetime.strptime(str(d2), '%Y-%m-%d')
        if date2.date() < date1.date():
            raise UnAcceptedValueError("Until date cannot be before start date")
        months = [dt.strftime("%m") for dt in rrule(MONTHLY, dtstart=date1, until=date2)]
        days = [day.strftime("%d") for day in rrule(DAILY, dtstart=date1, until=date2)]
        date_difference["months"] = abs(len(months) - 1)
        date_difference["days"] = abs(len(days))
        return date_difference

    def request_data(self, adults, children, source, destination, departure_date=None, number_of_nights=None,
                     query_start_date=None,
                     query_end_date=None):

        return_date = None
        if departure_date is not None:
            return_date = datetime.datetime.strptime(str(departure_date), '%Y-%m-%d') + timedelta(days=number_of_nights)
            return_date = return_date.date()
            departure_date = datetime.datetime.strptime(str(departure_date), '%Y-%m-%d').date()

        if query_start_date is not None:
            departure_date = query_start_date
            return_date = query_end_date

        if return_date is not None and departure_date is not None:
            if return_date < departure_date:
                raise UnAcceptedValueError("Return date cannot be before departure date")

        payload = {'Adultcount': adults, 'Childcount': children, 'DepartureDate': departure_date,
                   'Destination': destination,
                   'InfantCount': 0,
                   'Origin': source, 'ReturnDate': return_date, 'SelectedCurrencyCode': 'AUD', 'TripKind': 'return',
                   'onoffswitch': 'on',
                   '__RequestVerificationToken': self.csrf}
        headers = {
            'origin': "https://booking.tigerair.com.au",
            'upgrade-insecure-requests': "1",
            'dnt': "1",
            'content-type': "application/x-www-form-urlencoded",
            'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36",
            'accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            'cache-control': "no-cache"
        }
        response = self.session.post(url=self.url, data=payload, cookies=self.sessionCookies, headers=headers)
        soup = BeautifulSoup(response.text, 'lxml')
        return soup

    def get_lowest_flight_fare(self, trip_flights):
        fare_list = []
        lowest_fare = None
        flight_fares = trip_flights.find_all('td', attrs={'data-fare-type': 'Light Fare'})

        for fare in flight_fares:
            if fare.findChildren("span", {'class': 'currency'}):
                if not fare.findChildren('span', {'class': 'fares-remaining'}):
                    fare_list.append("".join(str(fare.get_text()).split()).strip("$"))
        if (len(fare_list)) >= 1:
            lowest_fare = (sorted(fare_list, key=float))[0]
        return lowest_fare

    def get_filtered_list(self, date_list, price_list, year_list, actual_end_date, list_date_object):

        self.header_date_fare["days_difference"] = self.get_date_difference(actual_end_date, list_date_object)
        self.header_date_fare["query_date_list"] = date_list[:-(self.header_date_fare["days_difference"]["days"])]
        self.header_date_fare["query_price_list"] = price_list[:-(self.header_date_fare["days_difference"]["days"])]
        self.header_date_fare["query_date_year"] = year_list[:-(self.header_date_fare["days_difference"]["days"])]
        return self.header_date_fare

    def get_header_date_fare(self, adult, children, source, destination, query_start_date, query_end_date):

        soup = self.request_data(adults=adult, children=children, source=source, destination=destination,
                                 query_start_date=query_start_date, query_end_date=query_end_date)

        query_price_list = []
        query_date_list = []
        list_last_year = []
        if query_start_date is self.current_date:
            today_from_flights = soup.find('table', {'id': 'table-0'})
            query_price_list.append(self.get_lowest_flight_fare(today_from_flights))

        if query_end_date is self.current_date:
            today_return_flights = soup.find('table', {'id': 'table-1'})
            query_price_list.append(self.get_lowest_flight_fare(today_return_flights))

        from_flights_header = soup.find('div', {'class': 'date-row'})

        for price in from_flights_header.find_all('li', {'class': 'js-cal-date-change date-change'}):

            if price.find('span'):
                query_price_list.append(price.find('span').get_text())

        for span in from_flights_header.find_all("span", {'class': 'lowest-day-fare'}):
            span.replaceWith('')

        for date in from_flights_header.find_all('li', {'class': 'js-cal-date-change date-change'}):
            if date.get_text() is not None:
                if date.has_attr('data-new-date'):
                    query_date_list.append(date.get_text())
                    if not date.find('img', {'class': 'nextDay'}):
                        if not date.find('img', {'class': 'prevDay'}):
                            list_last_year.append(date['data-new-date'])

        list_last_year = list(filter(None, list_last_year))
        query_date_list = list(filter(None, query_date_list))

        actual_new_query_start_date = datetime.datetime.strptime(str(query_start_date), '%Y-%m-%d').date() + timedelta(
            days=1)
        actual_new_query_end_date = datetime.datetime.strptime(str(query_end_date), '%Y-%m-%d').date() - timedelta(
            days=1)

        ui_format_query_start_date = datetime.datetime.strptime(str(actual_new_query_start_date), '%Y-%m-%d').strftime(
            '%a, %d %b')
        ui_format_query_end_date = datetime.datetime.strptime(str(actual_new_query_end_date), '%Y-%m-%d').strftime(
            '%a, %d %b')

        '''Iterate to pop out dates outside the start date'''
        while True:
            if query_date_list[0] != ui_format_query_start_date:
                query_date_list.pop(0)
                query_price_list.pop(0)
                list_last_year.pop(0)
            if query_date_list[0] == ui_format_query_start_date:
                break
        self.query_date_list.extend(query_date_list)
        self.query_price_list.extend(query_price_list)
        self.list_last_year.extend(list_last_year)

        self.header_date_fare["query_date_list"] = self.query_date_list
        self.header_date_fare["query_price_list"] = self.query_price_list

        list_last_year_date = self.list_last_year[len(self.list_last_year) - 1]
        list_last_year_date_obj = datetime.datetime.strptime(str(list_last_year_date), '%Y%m%d').date()

        self.header_date_fare["list_last_year"] = str(list_last_year_date_obj).split("-")[0]
        self.header_date_fare["query_date_year"] = self.list_last_year
        return self.header_date_fare

    def get_actual_trip_date_lowest_fare(self, adult, children, departure_date, number_of_nights, source, destination):
        trip_date_lowest_fare = {}

        soup = self.request_data(adults=adult, children=children, source=source, destination=destination,
                                 departure_date=departure_date, number_of_nights=number_of_nights,
                                 query_start_date=None,
                                 query_end_date=None)

        from_flights = soup.find('table', {'id': 'table-0'})
        trip_date_lowest_fare["lowest_from_flight"] = self.get_lowest_flight_fare(from_flights)

        to_flights = soup.find('table', {'id': 'table-1'})
        trip_date_lowest_fare["lowest_return_flight"] = self.get_lowest_flight_fare(to_flights)
        return trip_date_lowest_fare

    def get_query_period_lowest_fares(self, adult, children, source, destination, query_start_date, query_end_date,
                                      check_trend=False):

        number_of_days_to_query = self.get_date_difference(d1=query_start_date,
                                                           d2=query_end_date)
        query_period_lowest_fares = [{} for dict in range((number_of_days_to_query["days"]))]

        self.current_date = datetime.datetime.now().date().strftime('%Y-%m-%d')
        if query_start_date != self.current_date:
            new_query_start_date = datetime.datetime.strptime(query_start_date, '%Y-%m-%d').date() - timedelta(days=1)
        else:
            new_query_start_date = self.current_date
        if query_end_date == self.current_date:
            new_query_end_date = self.current_date
        else:
            new_query_end_date = datetime.datetime.strptime(query_end_date, '%Y-%m-%d').date() + timedelta(days=1)

        self.header_date_fare = self.get_header_date_fare(adult=adult, children=children, source=source,
                                                          destination=destination,
                                                          query_start_date=new_query_start_date,
                                                          query_end_date=new_query_end_date)

        query_end_date_object = datetime.datetime.strptime(str(new_query_end_date), '%Y-%m-%d').date()
        actual_end_date_object = datetime.datetime.strptime(str(query_end_date), '%Y-%m-%d').date()
        list_last_date = self.header_date_fare["query_date_list"][len(self.header_date_fare["query_date_list"]) - 1]
        list_date_object = datetime.datetime.strptime(str(list_last_date), '%a, %d %b').date().replace(
            year=int(self.header_date_fare["list_last_year"]))
        while True:

            if list_date_object > actual_end_date_object:
                self.header_date_fare = self.get_filtered_list(self.header_date_fare["query_date_list"],
                                                               self.header_date_fare["query_price_list"],
                                                               self.header_date_fare["query_date_year"],
                                                               query_end_date_object,
                                                               list_date_object)
                list_last_date = self.header_date_fare["query_date_list"][
                    len(self.header_date_fare["query_date_list"]) - 1]
                list_date_object = datetime.datetime.strptime(str(list_last_date), '%a, %d %b').date().replace(
                    year=int(self.header_date_fare["list_last_year"]))

            elif list_date_object < actual_end_date_object:
                query_start_date = list_date_object
                self.header_date_fare = self.get_header_date_fare(adult=adult, children=children, source=source,
                                                                  destination=destination,
                                                                  query_start_date=query_start_date,
                                                                  query_end_date=new_query_end_date)
                list_last_date = self.header_date_fare["query_date_list"][
                    len(self.header_date_fare["query_date_list"]) - 1]
                list_date_object = datetime.datetime.strptime(str(list_last_date), '%a, %d %b').date().replace(
                    year=int(self.header_date_fare["list_last_year"]))

            elif list_date_object == actual_end_date_object:
                break

        for date_fare in range(len(self.header_date_fare["query_date_list"])):
            query_period_lowest_fares[date_fare]["date"] = self.header_date_fare["query_date_list"][date_fare]
            query_period_lowest_fares[date_fare]["fare"] = self.header_date_fare["query_price_list"][date_fare]
            query_period_lowest_fares[date_fare]["year"] = self.header_date_fare["query_date_year"][date_fare]
        if check_trend:
            return query_period_lowest_fares
        else:
            lowest_fare_for_given_query = sorted(query_period_lowest_fares, key=lambda i: i['fare'])
            return lowest_fare_for_given_query[0]

    '''Question 1:
      Deﬁne a python class with a method for users to query the lowest price of the round-trip ﬂights from “Tiger Air”
      test_flight_trip_dates_lowest_fare - returns the exact from and return dates lowest price
      test_flight_query_period_lowest_fare - returns the lowest price for the given period with date and fare'''


    def test_flight_trip_dates_lowest_fare(self):
        '''To get the lowest price of the day for from and to flights for the given dates'''

        trip_date_lowest_fare = self.get_actual_trip_date_lowest_fare(adult=2, children=1, departure_date="2019-03-30",
                                                                      number_of_nights=3,
                                                                      source="MEL", destination="SYD")


    def test_flight_query_period_lowest_fare(self):

        ''''To get the header lower price list for the given query period '''

        from_flight_query_period_lowest_fares = self.get_query_period_lowest_fares(adult=2, children=1,
                                                                                   source="MEL",
                                                                                   destination="SYD",
                                                                                   query_start_date='2019-05-04',
                                                                                   query_end_date='2019-05-08')

        print(from_flight_query_period_lowest_fares)

        self.clear_class_objects()
        return_flight_query_period_lowest_fares = self.get_query_period_lowest_fares(adult=2, children=1,
                                                                                     source="SYD",
                                                                                     destination="MEL",
                                                                                     query_start_date='2019-04-04',
                                                                                     query_end_date='2019-04-08')
        print(return_flight_query_period_lowest_fares)

    '''Question 2: 
    With bokeh (or any other) library to output a Line chart to show the price trend into a html ﬁle which can be opened by browser'''

    def test_flight_price_trend_bokeh(self):

        self.clear_class_objects()

        tigerair_flight_fares = self.get_query_period_lowest_fares(adult=2, children=1,
                                                                   source="MEL",
                                                                   destination="SYD", query_start_date='2019-06-01',
                                                                   query_end_date='2019-06-05', check_trend=True)

        dates = [d['year'] for d in tigerair_flight_fares if 'year' in d]
        fares = [d['fare'] for d in tigerair_flight_fares if 'fare' in d]

        date_list = []
        for date in range(len(dates)):
            formatted_date = datetime.datetime.strptime((dates[date]), '%Y%m%d')
            date_list.append(formatted_date)

        fare_list = []
        for fare in range(len(fares)):
            fare_list.append(str(fares[fare]).strip("AUD "))

        fare_list = [float("".join(x.replace('"', ''))) for x in fare_list]
        print(fare_list)
        df = pd.DataFrame(data=fare_list,
                          index=date_list,
                          columns=['foo']
                          )

        p = figure(x_axis_type='datetime', title="Tiger Air Fare Trend", plot_width=1000, plot_height=500)
        p.line(df.index, df['foo'], legend="Fare", line_width=2, line_color="red")
        p.xaxis.formatter = DatetimeTickFormatter(
            hours=["%d %B %Y"],
            days=["%d %B %Y"],
            months=["%d %B %Y"],
            years=["%d %B %Y"],
        )
        p.xaxis.major_label_orientation = pi / 4
        output_file('TigerAir.html')
        show(p)
