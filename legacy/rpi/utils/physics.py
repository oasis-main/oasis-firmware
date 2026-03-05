import math

def vpd(temp: float, hum: float): #Temp in F, Hum in % 

    f = float(temp) #temperature farenheit
    t =	(5/9)*(f + 459.67) #temperature kelvin
    rh =  float(hum) #relative humidity

    #https://www.cs.helsinki.fi/u/ssmoland/physics/envphys/lecture_2.pdf
    a = 77.34 #empirically
    b = -7235 #fitted
    c = -8.2 #exponental
    d = 0.005711 #constants
    svp = math.e ** (a+(b/t)+(c*math.log(t))+d*t) #saturation vapor pressure

    #https://agradehydroponics.com/blogs/a-grade-news/how-to-calculate-vapour-pressure-deficit-vpd-via-room-temperature
    vpd_pa = (1 - (rh/100)) * svp #vapor pressure deficit in pascals
    vpd = vpd_pa / 1000 #convert vpd to kilopascals

    return round(vpd, 3)

def kwh(wattage: float, time_active): #time_active is an int or float, representing seconds
    
    kwh_used = (wattage/1000)*(time_active/3600)
    
    return round(kwh_used, 4)
