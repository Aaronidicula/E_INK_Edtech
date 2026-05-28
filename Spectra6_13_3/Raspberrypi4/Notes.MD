#personal notes

#write here
<br>crontab -e</br>

#Auto refresh every 30 minutes
*/30 7-22 * * * /home/robotpi/einkenv/bin/python3 /home/robotpi/Eink/RaspberryPi/python/examples/calendar_weekly_art.py --no-picker >> /home/robotpi/calendar.log 2>&1

#Auto refresh on every specific minute on every hour 
5 7-22 * * * /home/robotpi/einkenv/bin/python3 /home/robotpi/Eink/RaspberryPi/python/examples/calendar_weekly_art.py --no-picker >> /home/robotpi/calendar.log 2>&1
#^ for every 5th minute of every hour from 7am to 10pm //24hour format(22)//
