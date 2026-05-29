#personal notes

#write here
<br>crontab -e</br>

#Auto refresh every 30 minutes
<br>*/30 7-22 * * * /home/robotpi/einkenv/bin/python3 /home/robotpi/Eink/RaspberryPi/python/examples/calendar_weekly_art.py --no-picker >> /home/robotpi/calendar.log 2>&1</br>

#Auto refresh on every specific minute on every hour 
<br>5 7-22 * * * /home/robotpi/einkenv/bin/python3 /home/robotpi/Eink/RaspberryPi/python/examples/calendar_weekly_art.py --no-picker >> /home/robotpi/calendar.log 2>&1
#^ for every 5th minute of every hour from 7am to 10pm //24hour format(22)//</br>


*** For UI design use epaper_designer.py and in crontab -e use epaper_refresh.py for auto refresh ***
<br> After designing in epaper_designer.py save the png for your reference and save the config under the name *layout.json* that will be used for epaper_refresh.py for every auto refresh </br>

*For Gui (created for raspberry)*
<br> It is inside GUIsetup directory</br> <br> use epaper_designer.py to design layout either in pc or in pi and save config as layout.json </br> <br> use epaper_refresh.py in crontab -e for autorefresh. layout.json should be in same folder as epaper_refresh.py and give the execute command in crontab with python3 followed by the path to the script file. (_refer above_)</br> <br> if the libraries and tools are inside venv then run python3 inside venv and execute our script (_for more info read autorefresh line above_).</br>
