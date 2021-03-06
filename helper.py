import re
import csv
import json
import folium
import base64
import pandas as pd
from io import BytesIO
from string import capwords
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import country_converter as coco
from bs4 import BeautifulSoup as soup
from urllib.request import Request, urlopen


def parser(url):

    headers = {'User-Agent': 'Mozilla/5.0',
               'Referer': 'https://covid19.workpointnews.com/?to=THAILAND'}
    req = Request(url, headers=headers)

    # open up connection, grap the page
    uClient = urlopen(req)
    page_html = uClient.read()
    uClient.close()  # close connection

    # load data to json format for easy accessing
    page_json = json.loads(page_html)
    return page_json


def writeCSV(mode):
    if mode == 'cases':
        c = cases()
        df = c.getCasesData()
    elif mode == 'world':
        w = world()
        df = w.getWorldData()
    else:
        print("Wrong Mode")
        raise Exception

    # write to csv file
    csv = df.to_csv(index=False)
    with open('files/' + mode + '.csv', 'w') as fp:
        fp.write(csv)

    # write a timestamp of the file created
    with open('files/' + mode + 'LastUpdate.txt', 'w') as fp:
        fp.write(str(datetime.utcnow()))


class world:

    def getWorldData(self):
        url = "https://covid19.workpointnews.com/api/world"

        json = parser(url)

        data = {'Country': [], 'Confirmed': [], 'Recovered': [],
                'Death': [], 'Travel': []}

        for country in json['statistics']:
            if len(country['name']) > 15:  # length control
                continue

            data['Country'].append(country['name'])
            data['Confirmed'].append(country['confirmed'])
            data['Recovered'].append(country['recovered'])
            data['Death'].append(country['deaths'])
            data['Travel'].append(country['travel'])

        df = pd.DataFrame(data)  # convert to a dataframe
        # set Country as an index
        df.set_index('Country', inplace=True)
        # remove Country with no data
        df.dropna(axis=0, how='all', inplace=True)
        # Set index back to place
        df.reset_index(inplace=True)
        # convert float to int
        df.iloc[:, [1, 2, 3]] = df.iloc[:, [1, 2, 3]].astype(int)

        return df

    def getWorldHTML(self):
        try:
            # write a timestamp of last get data
            with open('files/worldLastUpdate.txt', 'r') as fp:
                timestamp = fp.read()

            now = datetime.utcnow()
            lastUpdate = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
            differ = now - lastUpdate

            # write new dataframe when more than 15 mins
            if differ.seconds > 15 * 60:
                writeCSV('world')  # timestamp get updated in here

            # read csv to get data
            df = pd.read_csv('files/world.csv', index_col=False)

        except FileNotFoundError:  # write new if not found
            writeCSV('world')  # timestamp get updated in here
            df = pd.read_csv('files/world.csv', index_col=False)

        df = df.fillna('')  # fill na with blank instead
        # Sort by Confirmed Cases
        df.sort_values(by='Confirmed', ascending=False,
                       inplace=True, ignore_index=True)

        # make index start at 1
        df.index += 1
        df.index.name = 'Rank'
        # make Rank as one of the columns
        df.reset_index(level=0, inplace=True)

        # for gradient
        sortedRecovered = df['Recovered'].to_list()
        sortedRecovered.sort(reverse=True)
        sortedDeath = df['Death'].to_list()
        sortedDeath.sort(reverse=True)

        # set style
        fontSize = '27pt'
        df = df.style.set_properties(**{'text-align': 'center',
                                        'border-color': 'black',
                                        'font-size': fontSize,
                                        'background-color': '#f7f1df',
                                        'color': 'black'})\
            .set_table_styles([{'selector': 'th', 'props': [('font-size', fontSize)]}])\
            .background_gradient(cmap='Oranges', subset='Confirmed', vmax=sum(df['Confirmed'][0:10].to_list())/10)\
            .background_gradient(cmap='Oranges', subset='Recovered', vmax=sum(sortedRecovered[0:11])/11)\
            .background_gradient(cmap='Oranges', subset='Death', vmax=sum(sortedDeath[0:5])/5)

        return df.hide_index().render()

    def getWorldMapHTML(self):
        try:
            df = pd.read_csv('files/world.csv', index_col=False)
        except FileNotFoundError:  # write new if not found
            writeCSV('world')  # timestamp get updated in here
            df = pd.read_csv('files/world.csv', index_col=False)

        # drop all dates except lastest
        df.drop(df.columns[2:], axis=1, inplace=True)
        df['Country'] = coco.convert(df['Country'].to_list(), to='ISO3')

        bins = list(df['Confirmed'].quantile([0, 0.7, 0.8, 0.99, 1]))

        try:
            with open('permanentfiles/worldCountry.json', 'r') as j:
                geo = json.loads(j.read())
        except FileNotFoundError:
            raise Exception

        # follium
        m = folium.Map(location=[0, 0], zoom_start=2, width=960, height=500)

        folium.Choropleth(
            geo_data=geo,
            name='COVID-19',
            data=df,
            columns=['Country', 'Confirmed'],
            key_on='feature.id',
            fill_color='Reds',
            fill_opacity=1,
            line_opacity=0.1,
            highlight=True,
            nan_fill_color='white',

            bins=bins,
            reset=True
        ).add_to(m)

        return m._repr_html_().replace('padding-bottom:60%;', 'padding-bottom:40%;')

    def getWorldTotal(self):
        total = pd.read_csv('files/world.csv', index_col=False)
        total.drop(['Country', 'Travel'], axis=1, inplace=True)
        total = total.sum().to_dict()

        return total


class cases:

    def getCasesData(self):
        url = "https://covid19.workpointnews.com/api/cases"

        json = parser(url)

        data = {'Number': [], 'Job': [], 'Origin': [],
                'Type': []}

        for case in json:
            data['Number'].append(case['number'])
            data['Job'].append(case['job'])
            data['Origin'].append(case['origin'])

            if case['type'] == None:
                data['Type'].append('-')
            else:
                # try to format type shorter
                p = re.compile(r'[0-9]{1}.{3}|[(]{1}.*?[)]{1}')
                data['Type'].append(p.sub('', case['type']))

        df = pd.DataFrame(data)  # convert to a dataframe

        return df

    def getCasesHTML(self):
        try:
            # get a timestamp of lastUpdate data
            with open('files/casesLastUpdate.txt', 'r') as fp:
                timestamp = fp.read()

            now = datetime.utcnow()
            lastUpdate = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
            differ = now - lastUpdate

            # write new dataframe when more than 15 mins
            if differ.seconds > 15 * 60:
                writeCSV('cases')  # timestamp get update in here

            # read csv to get data
            df = pd.read_csv('files/cases.csv', index_col=False)

        except FileNotFoundError:  # write new if not found
            writeCSV('cases')  # timestamp get update in here
            df = pd.read_csv('files/cases.csv', index_col=False)

        df = df.fillna('-')  # fill na with blank instead
        # Sort by Confirmed Cases
        df.sort_values(by='Number', ascending=False,
                       inplace=True, ignore_index=True)

        # set style
        fontSize = '20pt'
        df = df.style.set_properties(**{'text-align': 'center',
                                        'border-color': 'green',
                                        'font-size': fontSize,
                                        'background-color': '#fdfff7',
                                        'color': 'black'})\
            .set_table_styles([{'selector': 'th', 'props': [('font-size', fontSize)]}])\


        return df.hide_index().render()

    def getCasesSummary(self):
        # Summary of Thailand
        thai_json = parser("https://covid19.workpointnews.com/api/constants")

        data = {}
        data['recovered'] = thai_json['หายแล้ว']
        data['death'] = thai_json['เสียชีวิต']
        data['added'] = thai_json['เพิ่มวันนี้']
        data['hospitolized'] = thai_json['กำลังรักษา']
        data['confirmed'] = thai_json['ผู้ติดเชื้อ']

        return data


class country:
    def writeCountryTimeSeries(self):
        url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv'
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = Request(url, headers=headers)

        # open up connection, grap the page
        uClient = urlopen(req)
        page_csv = uClient.read().decode('utf-8').replace('Korea, South',
                                                          'South Korea').replace('Taiwan*', 'Taiwan').replace('US', 'United States')

        uClient.close()  # close connection

        now = datetime.utcnow()

        # try to get timestamp of the last update
        try:
            # write a timestamp of last get data
            with open('files/timeSeriesLastUpdate.txt', 'r') as fp:
                timestamp = fp.read()
            with open('files/timeseries.csv', 'r') as fp:
                pass
        except FileNotFoundError:  # never init any timeSeries file
            with open('files/timeSeriesLastUpdate.txt', 'w') as fp:
                fp.write(str(now))
                timestamp = str(now)
            with open('files/timeseries.csv', 'w') as fp:
                fp.write(page_csv)

        lastUpdate = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
        differ = now - lastUpdate

        # write new dataframe when more than 1 hour
        if differ.seconds > 60 * 60 * 1:
            with open('files/timeseries.csv', 'w') as fp:
                fp.write(page_csv)
            with open('files/timeSeriesLastUpdate.txt', 'w') as fp:
                fp.write(str(now))

    def getCountryPlot(self, country):

        # Caplitalize country params from url
        country = capwords(country)

        try:
            df = pd.read_csv('files/timeseries.csv', index_col=1)
        except FileNotFoundError:
            self.writeCountryTimeSeries()
            df = pd.read_csv('files/timeseries.csv', index_col=1)

        df = df.drop(columns=['Province/State', 'Lat', 'Long'])

        try:  # country appear only 1 in df
            ct = df.loc[country, :].to_frame()
            ct.index.name = 'Date'
            ct = ct.reset_index()
            ct['Date'] = pd.to_datetime(ct['Date'])
            date = ct['Date'].to_list()
            case = ct[country].to_list()

        except AttributeError:  # appear more than 1
            ct = df.loc[country, :]
            ct = ct.reset_index()

            aggregation_functions = {}
            for col in ct.columns[1:]:
                aggregation_functions[col] = 'sum'
            ct = ct.groupby(ct['Country/Region']
                            ).aggregate(aggregation_functions)

            date = pd.to_datetime(ct.columns)
            case = ct.loc[country, :].to_list()

        fig, ax = plt.subplots(figsize=(9, 8))
        ax.plot(date, case, linewidth=5)
        plt.xticks(fontsize=18)
        plt.yticks(fontsize=18)

        # format the Date axis
        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        # save to html
        tmp = BytesIO()
        plt.savefig(tmp, format='png')
        encoded = base64.b64encode(tmp.getvalue()).decode('ascii')

        return encoded

    def getCountryData(self, country):
        try:
            allDF = pd.read_csv('files/world.csv', index_col=0)
        except FileNotFoundError:
            writeCSV('world')
            allDF = pd.read_csv('files/world.csv', index_col=0)

        country = capwords(country)

        # select only row of country
        df = allDF.loc[country, ['Confirmed', 'Recovered', 'Death']]

        return df.to_list()

    def getEmojiName(self, country):
        country = capwords(country)

        # get emoji
        try:
            with open('permanentfiles/country.json', 'r') as fp:
                data = json.load(fp)

            for c in data['body']['contents']:
                emojiName = c['action']['label']
                print(emojiName)
                if country in emojiName:  # found our emoji name
                    return emojiName
            return country
        except Exception:
            return country


class news:
    def newsParser(self):
        url = "https://covid19.workpointnews.com/live-update"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = Request(url, headers=headers)

        # open up connection, grap the page
        uClient = urlopen(req)
        page_html = uClient.read()
        uClient.close()  # close connection

        # html parsing
        pageSoup = soup(page_html, "html.parser")
        return pageSoup

    def getNewsData(self):
        pageSoup = self.newsParser()

        jsonScript = json.loads(pageSoup.find(
            'script', type='application/json').text)

        news = jsonScript['props']['pageProps']['ssrLiveUpdatePosts']

        data = {}

        for new in news:
            p = re.compile(r'&#[0-9]{4};')
            data[p.sub(' ', new['title'])] = [
                new['link'], new['cover']['medium']]

        return data

    def writeNewsJSON(self):

        # write new timestamp
        with open('files/newsLastUpdate.txt', 'w') as fp:
            fp.write(str(datetime.utcnow()))

        # write new JSON
        flex = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "News",
                        "size": "xxl",
                        "style": "normal",
                        "weight": "bold",
                        "decoration": "none",
                        "position": "relative",
                        "align": "center",
                        "wrap": True,
                        "gravity": "center"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": []
            },
            "styles": {
                "header": {
                    "backgroundColor": "#fae1be"
                },
                "body": {
                    "backgroundColor": "#fff1de"
                }
            }
        }

        data = self.getNewsData()

        for new in data:
            title = new
            link = data[new][0]
            picLink = data[new][1]

            content = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "image",
                        "url": picLink,
                        "position": "relative",
                        "margin": "xs",
                        "align": "center",
                        "gravity": "center",
                        "size": "full",
                        "aspectRatio": "16:9",
                        "action": {
                            "type": "uri",
                            "label": "action",
                            "uri": link
                        },
                        "aspectMode": "cover"
                    },
                    {
                        "type": "text",
                        "text": title,
                        "size": "md",
                        "weight": "bold",
                        "style": "normal",
                        "decoration": "none",
                        "position": "relative",
                        "align": "center",
                        "gravity": "center",
                        "action": {
                            "type": "uri",
                            "label": "action",
                            "uri": link
                        },
                        "maxLines": 2,
                        "wrap": True
                    },
                    {
                        "type": "spacer",
                        "size": "md"
                    }
                ]
            }

            flex['body']['contents'].append(content)

        # end loop
        # write to JSON file
        with open('files/news.json', 'w', encoding='utf-8') as fp:
            json.dump(flex, fp, ensure_ascii=False, indent=4)

    def getNewsJSON(self):
        try:
            # read a timestamp of last get data
            with open('files/newsLastUpdate.txt', 'r') as fp:
                timestamp = fp.read()

            now = datetime.utcnow()
            lastUpdate = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
            differ = now - lastUpdate

            #  write again if more than 30 mins
            if differ.seconds > 30 * 60:
                self.writeNewsJSON()

            with open('files/news.json', 'r') as fp:
                newsJSON = json.load(fp)

            return newsJSON

        except FileNotFoundError or json.decoder.JSONDecodeError:  # not found file
            print('got here??')
            self.writeNewsJSON()  # write again

            with open('files/news.json', 'r') as fp:
                newsJSON = json.load(fp)

            return newsJSON
