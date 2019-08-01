import argparse 
import sys 
import requests 
from bs4 import BeautifulSoup
import urllib.parse as urlparse
from collections import defaultdict
import dateutil.parser
from dateutil.relativedelta import relativedelta
from datetime import datetime


def print_request_response(url, request_response, verbose=False):
    print('\n\n**************************************************************************************************')
    print('print_request_response:')
    print('\nurl:\n', url)
    print('\nr.request:\n', request_response.request)
    print('\nr.request.url:\n', request_response.request.url)
    print('\nr.status_code:\n', request_response.status_code)
    print('\nr.reason:\n', request_response.reason)
    print('\nr.status_code:\n', request_response.headers)
    print('\nr.headers:\n', request_response.request)
    print('\nr.request.headers:\n', request_response.request.headers)
    if verbose:
        print('\nr.text:\n', request_response.text)
    print('\nlen(r.text):\n', len(request_response.text), '\n\n')
    print('**************************************************************************************************\n')


def parse_car_conditions(condition_groups, verbose=False):
    """Return dictionary with car conditions"""

    if verbose:
        print(condition_groups)

    conditions_dict = defaultdict(list)
    for condition_group in condition_groups:
        # span tags have the condition e.g. odometer, title
        conditions = condition_group.find_all('span')
        for condition in conditions:
            # a condition is either separated as : separated key value
            # or just a one line text item, gettable by using beautiful
            # soup's text method
            condition_str = condition.text.strip().split(':')
            if len(condition_str) > 1:
                # if condition is a key value pair then update car 
                # condition dictionary e.g. odometer: 60000
                conditions_dict[condition_str[0].strip()].append(condition_str[1].strip())
            else:
                # otherwise add value under generic attribute
                conditions_dict["attribute"].append(condition_str[0].strip())
    if verbose:
        print(conditions_dict)
    return conditions_dict


def parse_time_posted(soup):
    """Zone agnostic parse of posting date for car"""
    time_posted = dateutil.parser.parse(soup.find('time').attrs['datetime']).replace(tzinfo=None)
    return time_posted


def parse_car_listing(details_url):
    """Scrape car details craigslist page for given url"""
    response = requests.get(details_url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # car conditions are grouped in p tags with class attrgroup
    condition_groups = soup.find_all('p', {'class': 'attrgroup'})
    car_attributes = parse_car_conditions(condition_groups)

    # add to conditions the time the car listing was created and the listing url
    time_posted = parse_time_posted(soup)
    car_attributes["time_posted"].append(time_posted)
    car_attributes["url"].append(details_url)
    
    # add to conditions the main heading on car details page (frequently has car price listed)
    posting_title = soup.find('h2', {'class': 'postingtitle'}).text.strip()
    car_attributes["posting_title"].append(posting_title)

    # add to conditions the posting body on car details page (frequently has car price listed)
    posting_body = soup.find('section', {'id': 'postingbody'}).text.strip()
    car_attributes["posting_body"].append(posting_body)

    return car_attributes


def get_craigslist_cars(city, sort_results, search_distance, postal, min_price, max_price, make, model, min_auto_year,
                        min_auto_miles, max_auto_miles, condition_1, condition_2, auto_cylinders, auto_title_status,
                        auto_transmission, max_results, verbose=False):
    """Search list of cars and trucks on craigslist"""
    
    # craigslist url for car listings for a city
    base_url = 'https://' + city + '.craigslist.org/'
    listings_url = urlparse.urljoin(base_url, 'search/eby/cto')

    if verbose:
        print('\n\nlistings_url:', listings_url)

    # search cragislist for given car attributes
    params = {'sort': sort_results,
              'search_distance': search_distance,
              'postal': postal,
              'min_price': min_price,
              'max_price': max_price,
              'auto_make_model': make + "+" + model,
              # 'min_auto_year': min_auto_year,
              # 'min_auto_miles': min_auto_miles,
              # # 'max_auto_miles': max_auto_miles,
              # # 'condition_1': condition_1,
              # # 'condition_2': condition_2,
              # 'auto_cylinders': auto_cylinders,
              # 'auto_title_status': auto_title_status,
              # 'auto_transmission': auto_transmission,
              }

    if verbose:
        print('\n\nparams:', params)

    response = requests.get(listings_url, params=params)

    if verbose:
        print_request_response(listings_url, response, verbose=verbose)

    html_soup = BeautifulSoup(response.text, 'html.parser')
    posts = html_soup.find_all('li', class_='result-row')

    # top level validation of first page
    if verbose:
        print('\n\ntype(posts):', type(posts))  # to double check that I got a ResultSet
        print('len(posts):', len(posts))  # to double check I got 120 (elements/page)
        if len(posts) == 0:
            sys.exit('\n\nposts is empty - no vehicles were returned from query')

        print('\n\n*********************************************************')
        print('*********************************************************')
        print('*********************************************************')
        print('\n\nposts[0]:', posts[0])
        print('*********************************************************')
        print('*********************************************************')
        print('*********************************************************\n\n')

        print('\n\nlist result-price for all posts:')
        for i, post in enumerate(posts):
            print('i: {}; result-price: {}'.format(i, post.find('span', class_='result-price').text.strip()))

    # each returned car listing is in a html span tag with class li
    car_listings = html_soup.find_all('li', class_='result-row')

    if verbose:
        print('\n\nlen(car_listings): {}'.format(len(car_listings)))

    cars = []

    for i, car in enumerate(car_listings):
        # get car details page link url
        if len(cars) >= max_results:
            break
        details_link = car.find('a').attrs['href']
        details_url = urlparse.urljoin(base_url, details_link)
        cars.append(parse_car_listing(details_url))

        if verbose:
            print('\n\ni: {}; details_url: {}'.format(i, details_url))

    return cars


def filter_cars(cars, max_mileage, unallpythonowed_conditions, num_weeks):
    """return cars with acceptable mileage, state, posting within time_range"""
    min_posting_date = datetime.now() - relativedelta(weeks=+2)
    filtered_cars = []

    for car in cars:
        odometer = None
        if "odometer" in car:
            odometer = car.get("odometer")[0]
        title = None
        if "title" in car:
            title = car.get("title")[0]

        time_posted = car.get("time_posted")[0]

        if odometer < max_mileage and title not in unallowed_conditions and time_posted >= min_posting_date:
            filtered_cars.append(car)

    return filtered_cars


def main():

    # https://sfbay.craigslist.org/search/eby/cto?
    # sort=pricedsc&
    # hasPic=1&
    # search_distance=10&
    # postal=94610&
    # min_price=4000&
    # max_price=10000&
    # auto_make_model=toyota+corolla&
    # min_auto_year=2008&
    # min_auto_miles=100000&
    # max_auto_miles=120000&
    # condition=30&
    # condition=40&
    # auto_cylinders=2&
    # auto_title_status=1&
    # auto_transmission=2

    parser = argparse.ArgumentParser(description="craigslist car finder", parents=())
    parser.add_argument("-c", "--city", default='sfbay', help='which city to search for')
    parser.add_argument("-d", "--sort_results", default='pricedsc', help='how to sort results')
    parser.add_argument("-e", "--search_distance", default='10', help='maximum distance from search zip')
    parser.add_argument("-f", "--postal", default='94610', help='search zip')
    parser.add_argument("-p", "--min_price", default='4000')
    parser.add_argument("-o", "--max_price", default='10000')
    parser.add_argument("-b", "--make", default='toyota', help='car make (brand)')
    parser.add_argument("-m", "--model", default='corolla', help='car model')
    parser.add_argument("-y", "--min_auto_year", default='2008')
    parser.add_argument("-a", "--min_auto_miles", default='100000',
                        help='minimum miles travelled by car before purchase')
    parser.add_argument("-i", "--max_auto_miles", default='120000',
                        help='maximum miles travelled by car before purchase')
    parser.add_argument("-c1", "--condition_1", default='30')  # 30 = excellent
    parser.add_argument("-c2", "--condition_2", default='40')  # 40 = good
    parser.add_argument("-g1", "--auto_cylinders", default='2')  # 2 = 4 cylinders
    parser.add_argument("-t1", "--auto_title_status", default='1')  # 1 = clean
    parser.add_argument("-x1", "--auto_transmission", default='2')  # 2 = automatic, 1 = manual
    parser.add_argument("-l", "--max_results", default=1000, help='limit to this number of results for cars returned')
    parser.add_argument("-w", "--week_range", default=2,
                        help='number of weeks to search car listings for starting from now')
    parser.add_argument("-v", "--verbose", default='False', help='print debug output')
    # parser.add_argument("-t", "--blacklist_titles", nargs='+', default=['salvage', 'rebuilt'],
    #                     help='List unacceptable states for car, e.g. You may want to filter out cars that '
    #                          'have been totalled or salvaged')
    # parser.add_argument("-o", "--output", help='write matching cars to file')
    # parser.add_argument("-w", "--week_range", default=2,
    #                     help='number of weeks to search car listings for starting from now')

    try:
        args, extra_args = parser.parse_known_args()
        if args.verbose == 'True':
            verbose = True
        else:
            verbose = False
        if verbose:
            print('\n\nargs:', args)
            print('\n\nextra_args:', extra_args)
    except Exception as e:
        print(e)
        sys.exit(1)

    all_cars = get_craigslist_cars(args.city, args.sort_results, args.search_distance, args.postal,
                                   args.min_price, args.max_price, args.make, args.model, args.min_auto_year,
                                   args.min_auto_miles, args.max_auto_miles, args.condition_1, args.condition_2,
                                   args.auto_cylinders, args.auto_title_status, args.auto_transmission,
                                   args.max_results, verbose=verbose)

    print('\n\nall_cars:')
    for i, car_attributes in enumerate(all_cars):
        print('\n\ncar #: {}'.format(i))
        for key, value in car_attributes.items():
            print('key: {}; value: {}'.format(key, value))

    sys.exit()

    filtered_cars = filter_cars(all_cars, args.maximum_odometer, args.blacklist_titles, args.week_range)
    print('\n\nfiltered_cars:', filtered_cars)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
