import numpy as np
import pandas as pd
import pickle
import os
import json
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from core import constants as c

def NPV(file_studycase,
        file_refcase,
        name_studycase,
        name_refcase,
        economic_data,
        path,
        name_economic,
        form,
        sep=';',
        dec=','):
    """
    Economic assesment 
    
    file_studycase: str study case name
    file_refcase: str ref case name
                    
    name_studycase: str name of study case results file.pkl
    name_refcase: str name of reference case results file.pkl
    
    economic_data: dictionary
        'REC': dictionary REC economic parameters definition
            'collective self consumption incentives': [€/kWh]
            'incentives redistribution': 0-100 how the incentives are redistributed between prosumers, consumers and REC manger
        'carrier_name': dictionary (repeat for reach considered carrier: electricity, hydrogen, gas)
            'purchase': [€/kWh] electricity, [€/Sm^3] gas and [€/kg] hydrogen
            'sales': [€/kWh] electricity, [€/Sm^3] gas and [€/kg] hydrogen
        'interest rate': 0-1 [rate/year]
        'inflation rate': -1-1 [rate/year] cost evolution of each carrier
        'investment year': time horizon for which to evaluate the economic analysis (must be a multiple of simulation_year in general.json)
                        
    output: NPV of each location in 'economic_assessment.pkl'
        
    """  
    # open file study_case and ref_case
    with open(os.path.join(path,f"{file_studycase}.json"),'r')  as f:        studycase  = json.load(f)
    with open(os.path.join(path,f"{file_refcase}.json"),'r')    as f:        refcase    = json.load(f)

    if economic_data['investment years'] % c.simulation_years != 0:
        raise ValueError(f"'simulation_years' has been set equal to {c.simulation_years} in general.py but the 'investement_years' has been set equal to {economic_data['investment years']} in energy_market.py. This is not correct because simulation_years must be a submultiple of investement_years.")
        
    years_factor = int(economic_data['investment years'] / c.simulation_years) # this factor is useful to match the length of the energy simulation with the length of the economic investment
    
    # open cost of componenets of studycase and refcase
    with open('results/pkl/tech_cost_'+name_studycase+'.pkl', 'rb')     as f:        tc     = pickle.load(f)        
    with open('results/pkl/tech_cost_'+name_refcase+'.pkl', 'rb')       as f:        tc0    = pickle.load(f)
    
    # open energy balances of study and reference case
    with open('results/pkl/balances_'+name_studycase+'.pkl', 'rb')  as f:        balances   = pickle.load(f)        
    with open('results/pkl/balances_'+name_refcase+'.pkl', 'rb')    as f:        balances0  = pickle.load(f)
    
    # open detailed production balances of study and reference case
    with open('results/pkl/production_'+name_studycase+'.pkl', 'rb')           as f: production  = pickle.load(f)
    with open('results/pkl/production_'+name_refcase+'.pkl', 'rb')           as f: production0  = pickle.load(f)
                 
    # check energy balances timestep and transforms the series into hourly values because the energy price is always given either on a hourly basis (electricity) or per unit of mass (gas and hydrogen)
    if c.timestep != 60:
        for location_name in balances:
            for carrier in balances[location_name]:
                for tech in balances[location_name][carrier]:
                    balances[location_name][carrier][tech] = balances[location_name][carrier][tech].reshape(-1, int(60/c.timestep)).sum(axis=1)*c.timestep/60
        for location_name in balances0:
            for carrier in balances0[location_name]:
                for tech in balances0[location_name][carrier]:
                    balances0[location_name][carrier][tech] = balances0[location_name][carrier][tech].reshape(-1, int(60/c.timestep)).sum(axis=1)*c.timestep/60
    
    # converting energy carriers and material streams expressed as mass flow rates into hourly values necessary for economic analysis purposes. kg/s to kg/h and Sm^3/s to Sm^3/h
    for location_name in balances:
        for carrier in balances[location_name]:
            if carrier in ['hydrogen','LP hydrogen','HP hydrogen','oxygen','process steam','gas','water']:
                for tech in balances[location_name][carrier]:
                    balances[location_name][carrier][tech] = balances[location_name][carrier][tech]*3600
    for location_name in balances0:
        for carrier in balances0[location_name]:
            if carrier in ['hydrogen','LP hydrogen','HP hydrogen','oxygen','process steam','gas','water']:
                for tech in balances0[location_name][carrier]:
                    balances0[location_name][carrier][tech] = balances0[location_name][carrier][tech]*3600
    
    results = {}                        # dictionary initialise economic results of each locations
    
    peakP = sum(location_name.get('PV', {}).get('peakP',0) for location_name in studycase.values()) + sum(location_name.get('wind', {}).get('Npower',0)for location_name in studycase.values())/1000  #calculate total nominal power of REC
    
    for location_name in tc:            # for reach location
        
        results[location_name] = {}     # dictionary initialise economic results
       
        # initialise cash flow:
        results[location_name]['CF_refcase'] = {  'OeM': np.zeros(economic_data['investment years']),
                                                  'Initial/Final Tank level': np.zeros(economic_data['investment years']),                                                                                                                                                
                                                  'green_hydrogen_incentives': np.zeros(economic_data['investment years']),                                                                                                                           
                                                  'Purchase': {},
                                                  'Sale': {},
                                                  'Refund': np.zeros(economic_data['investment years']),
                                                  'CSC': np.zeros(economic_data['investment years']),
                                                  'Tot': np.zeros(economic_data['investment years'])}        
        results[location_name]['CF_studycase'] = {'OeM': np.zeros(economic_data['investment years']),
                                                  'Initial/Final Tank level': np.zeros(economic_data['investment years']),                                                                                                                                                
                                                  'green_hydrogen_incentives': np.zeros(economic_data['investment years']),                                                                                                                           
                                                  'Purchase': {},
                                                  'Sale': {},
                                                  'Refund': np.zeros(economic_data['investment years']),
                                                  'CSC': np.zeros(economic_data['investment years']),
                                                  'Tot': np.zeros(economic_data['investment years'])}       
        results[location_name]['CF'] = {  'OeM': np.zeros(economic_data['investment years']),
                                          'Initial/Final Tank level': np.zeros(economic_data['investment years']),                                                                                                                                                
                                          'green_hydrogen_incentives': np.zeros(economic_data['investment years']),                                                                                                                   
                                          'Purchase': {},
                                          'Sale': {},
                                          'Refund': np.zeros(economic_data['investment years']),
                                          'CSC': np.zeros(economic_data['investment years']),
                                          'Tot': np.zeros(economic_data['investment years'])} 

        results[location_name]['I0_refcase']    = {} # MC initialise investment refcase
        results[location_name]['I0_studycase']  = {} # MC initialise investment studycase                                                                                                                                                                    
        results[location_name]['I0']            = {} # initialise initial investment           
        
        for tech_name in tc[location_name]:         # considering each technology in the location
        
            results[location_name]['I0_studycase'][tech_name] = tc[location_name][tech_name]['total cost'] # MC I0 studycase
            results[location_name]['CF_studycase']['OeM'][:] += - tc[location_name][tech_name]['OeM'] # OeM

            # replacements 
            if tc[location_name][tech_name]['replacement']['years'] == "ageing": # if replacement year is calculated according to ageing
                with open('results/pkl/ageing_'+name_studycase+'.pkl', 'rb') as f:
                    age = pickle.load(f)     
                    age = age[location_name][tech_name][0]
                    for a in age:
                        rep_time = int(a/8760)
                        results[location_name]['CF_studycase']['OeM'][rep_time] += - results[location_name]['I0_studycase'][tech_name] * tc[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
            else: # if replacement time is given
                rep_time = tc[location_name][tech_name]['replacement']['years']
                while rep_time < economic_data['investment years']: # if tech_name replacement happens before the end of the simulation
                    results[location_name]['CF_studycase']['OeM'][rep_time] += - results[location_name]['I0_studycase'][tech_name] * tc[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
                    rep_time += tc[location_name][tech_name]['replacement']['years']
            # NB no refund considered for replacements
                    
            # refund
            if tc[location_name][tech_name]['refund']['years'] == 0:
                results[location_name]['I0_studycase'][tech_name] = results[location_name]['I0_studycase'][tech_name]*(100-tc[location_name][tech_name]['refund']['rate'])/100
            else:
                yearly_refund = results[location_name]['I0_studycase'][tech_name]*tc[location_name][tech_name]['refund']['rate']/100 / tc[location_name][tech_name]['refund']['years'] # yearly refund [€]
                refunds = np.zeros(economic_data['investment years']) # array initialise
                refunds[:min(economic_data['investment years'],tc[location_name][tech_name]['refund']['years'])] = yearly_refund # array repet yearly refond 
                results[location_name]['CF_studycase']['Refund'] += refunds # add refund to Cash Flow
            
        for tech_name in tc0[location_name]:
            
            results[location_name]['I0_refcase'][tech_name] = tc0[location_name][tech_name]['total cost'] #MC IO refcase                                                                                                            
            results[location_name]['CF_refcase']['OeM'][:] += - tc0[location_name][tech_name]['OeM'] # OeM
            
            # replacements 
            if tc0[location_name][tech_name]['replacement']['years'] == "ageing": # if replacement year is calculated according to ageing
                with open('results/pkl/ageing_'+name_refcase+'.pkl', 'rb') as f:
                    age = pickle.load(f)     
                    age = age[location_name][tech_name][0]
                    for a in age:
                        rep_time = int(a/8760)
                        results[location_name]['CF_refcase']['OeM'][rep_time] += - results[location_name]['I0'][tech_name] * tc0[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
            else: # if replacement time is given
                rep_time = tc0[location_name][tech_name]['replacement']['years']
                while rep_time < economic_data['investment years']: # if tech_name replacement happens before the end of the simulation
                    results[location_name]['CF_refcase']['OeM'][rep_time] += - tc0[location_name][tech_name]['total cost'] * tc0[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
                    rep_time += tc0[location_name][tech_name]['replacement']['years']
            
       
        # energy sold and purchased in study case 
        for carrier in balances[location_name]:                           # for each carrier (electricity, hydrogen, gas, heat)     
            if carrier+' grid' in balances[location_name][carrier]:  
                               
                if type(economic_data[carrier]['sale']) == str:     # if the price series is given
                    sale_series = pd.read_csv(path+'/energy_price/'+economic_data[carrier]['sale'])['0'].to_numpy()
                    if len(sale_series) < 8762:                      # it means that the serie must be repeated for the simulation_length selected
                        sale_series = np.tile(sale_series,int(c.simulation_years))                         
                    sold = balances[location_name][carrier][carrier+' grid'] * sale_series
                else:                                               # if the price is always the same 
                    sold = balances[location_name][carrier][carrier+' grid'] * economic_data[carrier]['sale'] 
               
                sold = np.tile(sold,years_factor)
                sold = np.reshape(sold,(-1,8760))
                results[location_name]['CF_studycase']['Sale'][carrier]   = - sold.sum(axis=1,where=sold<0)
                results[location_name]['CF']['Sale'][carrier] = np.zeros(economic_data['investment years'])
                
                if type(economic_data[carrier]['purchase']) == str: # if the price series is given
                    purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data[carrier]['purchase'])['0'].to_numpy()
                    if len(purchase_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                        purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                                     
                    purchase = balances[location_name][carrier][carrier+' grid'] * purchase_serie
                else: # if the price is always the same 
                    purchase = balances[location_name][carrier][carrier+' grid'] * economic_data[carrier]['purchase']
               
                purchase = np.tile(purchase,years_factor)
                purchase = np.reshape(purchase,(-1,8760))
                results[location_name]['CF_studycase']['Purchase'][carrier]   = - purchase.sum(axis=1,where=purchase>0)
                results[location_name]['CF']['Purchase'][carrier] = np.zeros(economic_data['investment years']) 

            if carrier == 'electricity': # Electricity purchased even by PV and wind if not owned
            
                if 'wind' in studycase[location_name] and studycase[location_name]['wind']['owned'] == False:
                    purchase_wind = np.zeros(8760*c.simulation_years)
                    for tech_name in production[location_name][carrier]['wind']:
                        if tech_name not in ['Tot']:   # I'm considering even the electricity injected from wind into grid because if not owned the electricity must be all purchased (PPA as produced contract)
                                                        # If we'll decide to add the PPA simultaneous with wind production, which means buying only the needed electricity (at a higher price of course) carrier + ' grid' should be added to 'Tot'
                            purchase_wind += production[location_name][carrier]['wind'][tech_name]
                    
                    if type(economic_data['wind electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['wind electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                              
                        purchase = purchase_wind * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_wind * economic_data['wind electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results[location_name]['CF_studycase']['Purchase'][carrier] += - purchase.sum(axis=1)
                    
                if 'PV' in studycase[location_name] and studycase[location_name]['PV']['owned'] == False:
                    purchase_PV = np.zeros(8760*c.simulation_years)
                    for tech_name in production[location_name][carrier]['PV']:
                        if tech_name not in ['Tot']:    # I'm considering even the electricity injected from PV into grid because if not owned the electricity must be all purchased (PPA as produced contract)
                                                        # If we'll decide to add the PPA simultaneous with PV production contract, which means buying only the needed electricity (at a higher price of course) carrier + ' grid' should be added to 'Tot'                        
                            purchase_PV += production[location_name][carrier]['PV'][tech_name]
                    
                    if type(economic_data['pv electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['pv electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                              
                        purchase = purchase_PV * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_PV * economic_data['pv electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results[location_name]['CF_studycase']['Purchase'][carrier] += - purchase.sum(axis=1)

        # energy sold and purchased in reference case 
        for carrier in balances0[location_name]: # for each carrier (electricity, hydrogen, gas, heat)
            if carrier+' grid' in balances0[location_name][carrier]: 
                
                if type(economic_data[carrier]['sale']) == str:                           # if there is the price serie
                    sold = balances0[location_name][carrier][carrier+' grid'] * sale_series
                else: # if the price is always the same 
                    sold = balances0[location_name][carrier][carrier+' grid']*economic_data[carrier]['sale'] 
                
                sold = np.tile(sold,years_factor)
                sold = np.reshape(sold,(-1,8760))
                results[location_name]['CF_refcase']['Sale'][carrier] = -sold.sum(axis=1,where=sold<0)
                results[location_name]['CF']['Sale'][carrier] = np.zeros(economic_data['investment years'])

                if type(economic_data[carrier]['purchase']) == str: # if there is the price serie
                    purchase = balances0[location_name][carrier][carrier+' grid'] * purchase_serie
                else: # if the price is always the same 
                    purchase = balances0[location_name][carrier][carrier+' grid']*economic_data[carrier]['purchase']
              
                purchase = np.tile(purchase,years_factor)
                purchase = np.reshape(purchase,(-1,8760))
                results[location_name]['CF_refcase']['Purchase'][carrier] = -purchase.sum(axis=1,where=purchase>0)
                results[location_name]['CF']['Purchase'][carrier] = np.zeros(economic_data['investment years'])
         
            if carrier == 'electricity': # Electricity purchased even by PV and wind if not owned
            
                if 'wind' in refcase[location_name] and refcase[location_name]['wind']['owned'] == False:
                    purchase_wind = np.zeros(8760*c.simulation_years)
                    for tech_name in production0[location_name][carrier]['wind']:
                        if tech_name not in ['Tot']:   # I'm considering even the electricity injected from wind into grid because if not owned the electricity must be all purchased (PPA as produced contract)
                                                        # If we'll decide to add the PPA simultaneous with wind production, which means buying only the needed electricity (at a higher price of course) carrier + ' grid' should be added to 'Tot'
                            purchase_wind += production0[location_name][carrier]['wind'][tech_name]
                    
                    if type(economic_data['wind electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['wind electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                              
                        purchase = purchase_wind * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_wind * economic_data['wind electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results[location_name]['CF_refcase']['Purchase'][carrier] += - purchase.sum(axis=1)
                    
                if 'PV' in refcase[location_name] and refcase[location_name]['PV']['owned'] == False:
                    purchase_PV = np.zeros(8760*c.simulation_years)
                    for tech_name in production0[location_name][carrier]['PV']:
                        if tech_name not in ['Tot']:    # I'm considering even the electricity injected from PV into grid because if not owned the electricity must be all purchased (PPA as produced contract)
                                                        # If we'll decide to add the PPA simultaneous with PV production contract, which means buying only the needed electricity (at a higher price of course) carrier + ' grid' should be added to 'Tot'                        
                            purchase_PV += production[location_name][carrier]['PV'][tech_name]
                    
                    if type(economic_data['pv electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['pv electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                              
                        purchase = purchase_PV * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_PV * economic_data['pv electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results[location_name]['CF_refcase']['Purchase'][carrier] += - purchase.sum(axis=1)
        # REC incentives redistribution
        if 'REC' in economic_data:
            csc = balances[location_name]['electricity']['collective self consumption']
            if type(economic_data['REC']['collective self consumption incentives']) == str:     # if the pun price series is given (Italian legislation)
                pun = pd.read_csv(path+'/energy_price/'+economic_data['REC']['collective self consumption incentives'])['0'].to_numpy()
                if len(pun) < (c.HOURS_YEAR+2):                   # it means that the serie must be repeated for the simulation_length selected
                    pun = np.tile(pun,int(c.simulation_years))
                # check su potenza nominale impianto
                if peakP > 600:
                    csc_inc = [min(0.100, (0.060 + max(0,0.180-i))) for i in pun]
                elif peakP > 200 and peakP <= 600:
                    csc_inc = [min(0.110, (0.070 + max(0,0.180-i))) for i in pun]
                else:
                    csc_inc = [min(0.120, (0.080 + max(0,0.180-i))) for i in pun]
                for i in range(len(csc_inc)):
                    csc_inc[i] += 0.008    #ARERA
                
                #PV incentives adjustment for the central and northern regions
                if 'region' in economic_data['REC']:
                    region = economic_data['REC']['region']
                    centro = ['Lazio', 'Marche', 'Toscana', 'Umbria', 'Abruzzo']
                    nord = ['Emilia-Romagna', 'Friuli-Venezia Giulia', 'Liguria', 'Lombardia', 'Piemonte',
                            'Trentino-Alto Adige/Südtirol', "Valle d'Aosta/Vallée d'Aoste", "Veneto"]
                    if region in centro:
                        for i in range(len(csc_inc)):
                            csc_inc[i] += 0.004
                    elif region in nord:
                        for i in range(len(csc_inc)):
                            csc_inc[i] += 0.010
            
            else:
                csc_inc = economic_data['REC']['collective self consumption incentives']
    
            inc_pro = - csc * economic_data['REC']['incentives redistribution']['producers']/100 * csc_inc
            inc_pro = np.tile(inc_pro,years_factor)
            inc_pro = np.reshape(inc_pro,(-1,8760))    
            results[location_name]['CF_studycase']['CSC'] += inc_pro.sum(axis=1,where=inc_pro>0) 
            
            inc_con = csc * economic_data['REC']['incentives redistribution']['consumers']/100 * csc_inc
            inc_con= np.tile(inc_con,years_factor)
            inc_con = np.reshape(inc_con,(-1,8760))
            results[location_name]['CF_studycase']['CSC'] += inc_con.sum(axis=1,where=inc_con>0)   
        

        # CF update considering inflation on each carrier
        for carrier in economic_data['inflation rate']:
            f = economic_data['inflation rate'][carrier]
            
            if carrier in results[location_name]['CF_studycase']['Purchase']:
                for y in range(economic_data['investment years']):
                    results[location_name]['CF_studycase']['Purchase'][carrier][y] = results[location_name]['CF_studycase']['Purchase'][carrier][y]*(1+f)**y
                    
            if carrier in results[location_name]['CF_studycase']['Sale']:
                for y in range(economic_data['investment years']):
                    results[location_name]['CF_studycase']['Sale'][carrier][y] = results[location_name]['CF_studycase']['Sale'][carrier][y]*(1+f)**y
                    
            if carrier in results[location_name]['CF_refcase']['Purchase']:
                for y in range(economic_data['investment years']):
                    results[location_name]['CF_refcase']['Purchase'][carrier][y] = results[location_name]['CF_refcase']['Purchase'][carrier][y]*(1+f)**y
                    
            if carrier in results[location_name]['CF_refcase']['Sale']:
                for y in range(economic_data['investment years']):
                    results[location_name]['CF_refcase']['Sale'][carrier][y] = results[location_name]['CF_refcase']['Sale'][carrier][y]*(1+f)**y
            
        if 'H tank' in tc[location_name]: # If final tank level is higher than initial one, the difference can be sold; purchased in the opposite case. The same process repetaed for each year
            with open('results/pkl/LOC_'+name_studycase+'.pkl', 'rb') as f: loc = pickle.load(f)
            loc = loc[location_name]['H tank'][:-1] # I want a number multiple of 8760 so the lasy component is deleted
            loc = [loc[i] for i in range(0, len(loc), int(60/c.timestep))] # force hourly timestep 
            loc = np.tile(loc,years_factor)
            loc = np.reshape(loc,(-1,8760))
            diff_values = loc[:, -1] - loc[:, 0] # If final tank level is higher than initial one, the difference can be sold; purchased in the opposite case. The same process repetaed for each year
            
            if type(economic_data['hydrogen']['sale']) == str:
                sale_serie = pd.read_csv(path+'/energy_price/'+economic_data['hydrogen']['sale'])['0'].to_numpy()
                if len(sale_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    sale_serie = np.tile(sale_serie,economic_data['investment years'])
                sale_serie = np.reshape(sale_serie,(-1,8760))
                sale_values = np.mean(sale_serie, axis=1)  #€/kg
            else:
                sale_values = np.tile(economic_data['hydrogen']['sale'],economic_data['investment years'])  #€/kg

            if type(economic_data['hydrogen']['purchase']) == str:
                purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['hydrogen']['purchase'])['0'].to_numpy()
                if len(purchase_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    purchase_serie = np.tile(purchase_serie,economic_data['investment years'])
                purchase_serie = np.reshape(purchase_serie,(-1,8760))
                purchase_values = np.mean(purchase_serie, axis=1)  #€/kg
            else:
                purchase_values = np.tile(economic_data['hydrogen']['purchase'],economic_data['investment years'])  #€/kg

            results[location_name]['CF_studycase']['Initial/Final Tank level'] = np.where(diff_values <= 0, diff_values * purchase_values, diff_values * sale_values)
            results[location_name]['CF_studycase']['Tot'] += results[location_name]['CF_studycase']['Initial/Final Tank level']
            
        if 'H tank' in tc0[location_name]:
            with open('results/pkl/LOC_'+name_refcase+'.pkl', 'rb') as f: loc = pickle.load(f)
            loc = loc[location_name]['H tank'][:-1] # I want a number multiple of 8760 so the lasy component is deleted
            loc = [loc[i] for i in range(0, len(loc), int(60/c.timestep))] # force hourly timestep 
            loc = np.tile(loc,years_factor)
            loc = np.reshape(loc,(-1,8760))
            diff_values = loc[:, -1] - loc[:, 0] # If final tank level is higher than initial one, the difference can be sold; purchased in the opposite case. The same process repeated each year
            
            if type(economic_data['hydrogen']['sale']) == str:
                sale_serie = pd.read_csv(path+'/energy_price/'+economic_data['hydrogen']['sale'])['0'].to_numpy()
                if len(sale_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    sale_serie = np.tile(sale_serie,economic_data['investment years'])
                sale_serie = np.reshape(sale_serie,(-1,8760))
                sale_values = np.mean(sale_serie, axis=1)  #€/kg
            else:
                sale_values = np.tile(economic_data['hydrogen']['sale'],economic_data['investment years'])  #€/kg

            if type(economic_data['hydrogen']['purchase']) == str:
                purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['hydrogen']['purchase'])['0'].to_numpy()
                if len(purchase_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    purchase_serie = np.tile(purchase_serie,economic_data['investment years'])
                purchase_serie = np.reshape(purchase_serie,(-1,8760))
                purchase_values = np.mean(purchase_serie, axis=1)  #€/kg
            else:
                purchase_values = np.tile(economic_data['hydrogen']['purchase'],economic_data['investment years'])  #€/kg

            results[location_name]['CF_refcase']['Initial/Final Tank level'] = np.where(diff_values <= 0, diff_values * purchase_values, diff_values * sale_values)
            results[location_name]['CF_refcase']['Tot'] += results[location_name]['CF_refcase']['Initial/Final Tank level']
 

        if 'electrolyzer' in tc[location_name] and economic_data['green_hydrogen_incentives']['application'] == True: # If hydrogen incentives have to be considered
            incentive_value = economic_data['green_hydrogen_incentives']['value']
            n_years_incentives = int(economic_data['green_hydrogen_incentives']['n_years'])
            if n_years_incentives >= int(c.simulation_years):
                mult_factor = int(n_years_incentives/int(c.simulation_years))
                h2_produced = np.tile(balances[location_name]['hydrogen']['electrolyzer'],mult_factor)
            else:
                h2_produced = balances[location_name]['hydrogen']['electrolyzer'][0:(8760*n_years_incentives)]
            
            h2_produced = np.reshape(h2_produced,(-1,8760))
            results[location_name]['CF_studycase']['green_hydrogen_incentives'][0:n_years_incentives] = np.sum(h2_produced, axis=1)*incentive_value
            results[location_name]['CF_studycase']['Tot'] += results[location_name]['CF_studycase']['green_hydrogen_incentives']
                
        if 'electrolyzer' in tc0[location_name] and economic_data['green_hydrogen_incentives']['application'] == True: # If hydrogen incentives have to be considered
            incentive_value = economic_data['green_hydrogen_incentives']['value']
            n_years_incentives = int(economic_data['green_hydrogen_incentives']['n_years'])
            if n_years_incentives >= int(c.simulation_years):
                mult_factor = int(n_years_incentives/int(c.simulation_years))
                h2_produced = np.tile(balances[location_name]['hydrogen']['electrolyzer'],mult_factor)
            else:
                h2_produced = balances[location_name]['hydrogen']['electrolyzer'][0:(8760*n_years_incentives)]
              
            h2_produced = np.reshape(h2_produced,(-1,8760))
            results[location_name]['CF_refcase']['green_hydrogen_incentives'][0:n_years_incentives] = np.sum(h2_produced, axis=1)*incentive_value
            results[location_name]['CF_refcase']['Tot'] += results[location_name]['CF_refcase']['green_hydrogen_incentives']
        
        # Calculate CF comparing CF_studycase and CF_refcase and total cash flow calculation
        results[location_name]['CF']['green_hydrogen_incentives'] += results[location_name]['CF_studycase']['green_hydrogen_incentives'] - results[location_name]['CF_refcase']['green_hydrogen_incentives']                                                                                                                                                                                                            
        results[location_name]['CF']['Initial/Final Tank level'] += results[location_name]['CF_studycase']['Initial/Final Tank level'] - results[location_name]['CF_refcase']['Initial/Final Tank level']
        results[location_name]['CF']['OeM'] += results[location_name]['CF_studycase']['OeM'] -results[location_name]['CF_refcase']['OeM'] 
        results[location_name]['CF']['Refund'] += results[location_name]['CF_studycase']['Refund'] -results[location_name]['CF_refcase']['Refund']
        results[location_name]['CF']['CSC'] += results[location_name]['CF_studycase']['CSC'] -results[location_name]['CF_refcase']['CSC']
        
        results[location_name]['CF_studycase']['Tot'] += results[location_name]['CF_studycase']['OeM']
        results[location_name]['CF_studycase']['Tot'] += results[location_name]['CF_studycase']['Refund']
        results[location_name]['CF_studycase']['Tot'] += results[location_name]['CF_studycase']['CSC']
        results[location_name]['CF_refcase']['Tot'] += results[location_name]['CF_refcase']['OeM']
        results[location_name]['CF_refcase']['Tot'] += results[location_name]['CF_refcase']['Refund']
        results[location_name]['CF_refcase']['Tot'] += results[location_name]['CF_refcase']['CSC']
      
        for carrier in results[location_name]['CF_studycase']['Purchase']:
            results[location_name]['CF_studycase']['Tot'] += results[location_name]['CF_studycase']['Purchase'][carrier]
            results[location_name]['CF']['Purchase'][carrier] += results[location_name]['CF_studycase']['Purchase'][carrier]
       
        for carrier in results[location_name]['CF_refcase']['Purchase']:
            results[location_name]['CF_refcase']['Tot'] += results[location_name]['CF_refcase']['Purchase'][carrier]
            results[location_name]['CF']['Purchase'][carrier] += - results[location_name]['CF_refcase']['Purchase'][carrier]
        
        for carrier in results[location_name]['CF_studycase']['Sale']:
            results[location_name]['CF_studycase']['Tot'] += results[location_name]['CF_studycase']['Sale'][carrier]
            results[location_name]['CF']['Sale'][carrier] += results[location_name]['CF_studycase']['Sale'][carrier]
        
        for carrier in results[location_name]['CF_refcase']['Sale']:
            results[location_name]['CF_refcase']['Tot'] += results[location_name]['CF_refcase']['Sale'][carrier]
            results[location_name]['CF']['Sale'][carrier] += - results[location_name]['CF_refcase']['Sale'][carrier]
        
        results[location_name]['CF']['Tot'] = results[location_name]['CF_studycase']['Tot'] - results[location_name]['CF_refcase']['Tot']
        
        #MC calculate I0 refcase
        results[location_name]['I0_refcase']['Tot'] = 0
        for tech_name in results[location_name]['I0_refcase']:
            if tech_name != 'Tot':
                results[location_name]['I0_refcase']['Tot'] += results[location_name]['I0_refcase'][tech_name]
                
        #MC calculate I0 studycase
        results[location_name]['I0_studycase']['Tot'] = 0
        for tech_name in results[location_name]['I0_studycase']:
             if tech_name != 'Tot':
                 results[location_name]['I0_studycase']['Tot'] += results[location_name]['I0_studycase'][tech_name]
        
        #MC calculate IO
        for tech_name in tc[location_name]:
            if tech_name in tc0[location_name]:
                if results[location_name]['I0_studycase'][tech_name] >= results[location_name]['I0_refcase'][tech_name]:
                    results[location_name]['I0'][tech_name] = results[location_name]['I0_studycase'][tech_name] - results[location_name]['I0_refcase'][tech_name]
                else:
                    results[location_name]['I0'][tech_name] = results[location_name]['I0_studycase'][tech_name]
            else:
                results[location_name]['I0'][tech_name] = results[location_name]['I0_studycase'][tech_name]


        results[location_name]['I0']['Tot'] = 0
        for tech_name in results[location_name]['I0']:
            if tech_name != 'Tot':
                results[location_name]['I0']['Tot'] += results[location_name]['I0'][tech_name]
            
        # calculate NPV
        results[location_name]['NPV'] = np.zeros(economic_data['investment years']+1) # array initialise Net Present Value
        results[location_name]['NPV'][0] = -results[location_name]['I0']['Tot'] # NPV at time 0 is - the initial investment
        i = economic_data['interest rate'] # interest rate [%]
        
        PBT = -1
        for y in range(1,economic_data['investment years']+1): # for each year
            aux_var = results[location_name]['NPV'].sum(where=results[location_name]['NPV']>0)
            results[location_name]['NPV'][y] = results[location_name]['NPV'][y-1] + results[location_name]['CF']['Tot'][y-1]/(1+i)**y # calculate NPV
            if aux_var == 0 and results[location_name]['NPV'][y-1] < 0 and results[location_name]['NPV'][y] >= 0:
                PBT = y-1+(-results[location_name]['NPV'][y-1]/(-results[location_name]['NPV'][y-1]+results[location_name]['NPV'][y]))
        
        if PBT > 0:
            results[location_name]['PBT'] = PBT
            results[location_name]['PI'] = results[location_name]['NPV'][-1]/results[location_name]['I0']['Tot']
        else:
            results[location_name]['PBT'] = np.nan
            results[location_name]['PI'] = np.nan
        
    if form == 'pkl':
        # save results in Results/economic_assesment.pkl
        with open(f"results/pkl/economic_assessment_{name_economic}.pkl", 'wb') as f:  pickle.dump(results,f) 
        
    if form == 'csv':
        df1 = {} #cashflow
        df2 = {} #I0
        df3 = {} #NPV
        for loc_name in results:
            # cash_flow.csv
            for cf in ['CF','CF_refcase','CF_studycase']:
                for field in results[loc_name][cf]:
                    if isinstance(results[loc_name][cf][field],dict):
                        for carrier in results[loc_name][cf][field]:
                            key = f"{loc_name} - {cf} - {field} - {carrier}"  
                            df1[key] = results[loc_name][cf][field][carrier]       
                    else:
                        key = f"{loc_name} - {cf} - {field}"               
                        df1[key] = results[loc_name][cf][field]
                        
            #I0
            for i0 in ['I0','I0_refcase','I0_studycase']:
                for tech in results[loc_name][i0]:
                    key = f"{loc_name} - {i0} - {tech}"
                    df2[key] = results[loc_name][i0][tech]                
            # npv.csv
            df3[f"{loc_name} - NPV"] = results[loc_name]['NPV']

        df1 = pd.DataFrame(df1)
        df1 = df1.round(4)
        df1.to_csv('results/csv/cash_flow_'+name_economic+'.csv',index=False,sep=sep,decimal=dec)
        
        df2 = pd.DataFrame(df2, index=['€'])
        df2 = df2.round(4)
        df2.to_csv('results/csv/I0_'+name_economic+'.csv',index=False,sep=sep,decimal=dec)
        
        df3 = pd.DataFrame(df3)
        df3 = df3.round(4)
        df3.to_csv('results/csv/NPV_'+name_economic+'.csv',index=False,sep=sep,decimal=dec)
        
                
def LCOH (location_name,
          structure,    
          name_studycase, 
          economic_data,
          path, 
          revenues    = False, 
          refund      = False,
          plot        = False,
          print_      = False):
    """
    Levelized Cost Of Hydrogen Calculation
    ----------
    location_name: str - location_name
    
    structure: dict - studycase                           
    
    name_studycase: str name of study case results file.pkl

    economic_data: dictionary
        'REC': dictionary REC economic parameters definition
            'collective self consumption incentives': [€/kWh]
            'incentives redistribution': 0-100 how the incentives are redistributed between prosumers, consumers and REC manger
        'carrier_name': dictionary (repeat for reach considered carrier: electricity, hydrogen, gas)
            'purchase': [€/kWh] electricity, [€/Sm^3] gas and [€/kg] hydrogen
            'sales': [€/kWh] electricity, [€/Sm^3] gas and [€/kg] hydrogen
        'interest rate': 0-1 [rate/year]
        'inflation rate': -1-1 [rate/year] cost evolution of each carrier
        'decommissioning': 0-1 [-] system dismantling as a % of initial construction costs (Total CAPEX)
        'investment year': time horizon for which to evaluate the economic analysis (must be a multiple of simulation_year in general.json)
         
    path: str path of the input data folder 
    
    revenues: list/tuple of str/bool defining if generated revenues from excess energy streams have to be included in the calculation. In case the carrier name(s) is/are specified. Default = False
    
    refund: boolean value defining refund cash flows have to be included in the calculation. Default = False
                        
    output:  [€/kgH2] float value of LCOH for the considered configuration

    """  

    if 'electrolyzer' in structure[location_name]:
        pass
    else:
        raise ValueError("Error: Electrolyzer is not employed in the system. Include it to calculate the LCOH.")
    years_factor = int(economic_data['investment years'] / c.simulation_years) # this factor is useful to match the length of the energy simulation with the length of the economic investment
    
    if economic_data['investment years'] % c.simulation_years != 0:
        raise ValueError(f"'simulation_years' has been set equal to {c.simulation_years} in general.py but the 'investement_years' has been set equal to {economic_data['investment years']} in energy_market.py. This is not correct because simulation_years must be a submultiple of investement_years.")
        
    # open cost of componenets of studycase
    with open('results/pkl/tech_cost_'+name_studycase+'.pkl', 'rb') as f:       tc = pickle.load(f)   # !!! to be double-checked for sensitivity analysis  
    
    with open('results/pkl/consumption_'+name_studycase+'.pkl', 'rb')           as f: consumption  = pickle.load(f) 
    with open('results/pkl/production_'+name_studycase+'.pkl', 'rb')           as f: production  = pickle.load(f)
    # check for hydrogen carrier to be included in location balances
    if len(production[location_name]['hydrogen']['electrolyzer']['Tot']) != 0:    # if hydrogen dictionary has values for the considered location
        pass
    else:
        print("\nHydrogen carrier not included in "+location_name+" location - LCOH calculation not available")
        return    
    
    # check energy balances timestep and transforms the series into hourly values because the energy price is always given either on a hourly basis (electricity) or per unit of mass (gas and hydrogen)
    if c.timestep != 60:
        # Number of steps per hour based on the timestep
        steps_per_hour = 60 // c.timestep          
        # Iterate over the electricity consumption dictionary
        for carrier in consumption[location_name]:
            for tech_name in consumption[location_name][carrier]:
                for tech_name1 in consumption[location_name][carrier][tech_name]:
                    consumption[location_name][carrier][tech_name][tech_name1] = consumption[location_name][carrier][tech_name][tech_name1].reshape(-1, steps_per_hour).sum(axis=1)*(c.timestep/60)
        # Iterate over the electricity production dictionary
        for carrier in production[location_name]:
            for tech_name in production[location_name][carrier]:
                for tech_name1 in production[location_name][carrier][tech_name]:
                    production[location_name][carrier][tech_name][tech_name1] = production[location_name][carrier][tech_name][tech_name1].reshape(-1, steps_per_hour).sum(axis=1)*(c.timestep/60)

   
    # balances are now in the form of yearly arrays of 8760 values. Converting energy carriers and material streams expressed as mass flow rates into hourly values necessary for economic analysis purposes. kg/s to kg/h and Sm^3/s to Sm^3/h
    for carrier in consumption[location_name]:
        if carrier in ['hydrogen','LP hydrogen','HP hydrogen','oxygen','process steam','gas','water']:
            for tech_name in consumption[location_name][carrier]:
                for tech_name1 in consumption[location_name][carrier][tech_name]:
                    consumption[location_name][carrier][tech_name][tech_name1] = consumption[location_name][carrier][tech_name][tech_name1]*3600
    
    for carrier in production[location_name]:
        if carrier in ['hydrogen','LP hydrogen','HP hydrogen','oxygen','process steam','gas','water']:
            for tech_name in production[location_name][carrier]:
                for tech_name1 in production[location_name][carrier][tech_name]:
                    production[location_name][carrier][tech_name][tech_name1] = production[location_name][carrier][tech_name][tech_name1]*3600
    results_pp  = {}    # dictionary initialising global lcoh results of each location
    lcoh        = {}    # dictionary initialising specific lcoh results of each location
        
    results_pp[location_name]   = {}    # dictionary initialising economic results_pp
    lcoh[location_name]         = {}    # dictionary initialising economic results_pp
    
    # initialise cash flow:     
    results_pp[location_name]['CF'] = {'OeM'        : np.zeros(economic_data['investment years']),
                                       'Purchase'   : {},
                                       'Sale'       : {},
                                       'Refund'     : np.zeros(economic_data['investment years']),
                                       'Tot'        : np.zeros(economic_data['investment years'])} 

    results_pp[location_name]['I0'] = {} # initialise initial investment
    
    lcoh[location_name]['Capex']    = {}
    lcoh[location_name]['Opex']     = {}
    
    for tech_name in tc[location_name]:              # considering each technology in the location
        
        if tech_name != 'fuel cell':    # Fuel cell not included in LCOH calculation

            results_pp[location_name]['I0'][tech_name] = tc[location_name][tech_name]['total cost'] # I0   
            results_pp[location_name]['CF']['OeM'][:] += - tc[location_name][tech_name]['OeM'] # OeM
            
            lcoh[location_name]['Capex'][tech_name] = np.concatenate(([tc[location_name][tech_name]['total cost']], np.full(economic_data['investment years'], 0))) # Capex array
            lcoh[location_name]['Opex'][tech_name]  = np.repeat(tc[location_name][tech_name]['OeM'],economic_data['investment years']) # Opex array  
            
            # replacements 
            if tc[location_name][tech_name]['replacement']['years'] == "ageing": # if replacement year is calculated according to ageing
                with open('results/pkl/ageing_'+name_studycase+'.pkl', 'rb') as f:
                    age = pickle.load(f)     
                    age = age[location_name][tech_name][0]
                    for a in age:
                        rep_time = int(a/8760)
                        results_pp[location_name]['CF']['OeM'][rep_time] += - results_pp[location_name]['I0'][tech_name] * tc[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
                        lcoh[location_name]['Capex'][tech_name] += lcoh[location_name]['Capex'][tech_name] * tc[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
            else: # if replacement time is given
                rep_time = tc[location_name][tech_name]['replacement']['years']
                while rep_time < economic_data['investment years']: # if tech_name replacement happens before the end of the simulation
                    results_pp[location_name]['CF']['OeM'][rep_time-1] += - np.float64(results_pp[location_name]['I0'][tech_name])*np.float64(tc[location_name][tech_name]['replacement']['rate'])/np.float64(100) # subtract technology replacement to location Cash Flow. -1 subtracted to index because the array is shifted of 1 position during LCOH calculation -> CF[1:]  = results_pp[location_name]['CF']['Tot'].copy()    # [€] Cash Flows
                    lcoh[location_name]['Capex'][tech_name][rep_time] += np.float64(lcoh[location_name]['Capex'][tech_name][0])*np.float64(tc[location_name][tech_name]['replacement']['rate'])/np.float64(100) # subtract technology replacement to location Cash Flow. np.float type added to avoid overflow problems 
                    rep_time += tc[location_name][tech_name]['replacement']['years']
            
            if refund: # if refund has to be included in LCOH calculation
                    
                if tc[location_name][tech_name]['refund']['years'] == 0 and tc[location_name][tech_name]['refund']['rate'] == 0:  # no refunds considered
                    pass
                elif tc[location_name][tech_name]['refund']['years'] == 0 and tc[location_name][tech_name]['refund']['rate'] != 0:
                    results_pp[location_name]['I0'][tech_name] = results_pp[location_name]['I0'][tech_name]*((100-tc[location_name][tech_name]['refund']['rate'])/100)
                    lcoh[location_name]['Capex'][tech_name] = lcoh[location_name]['Capex'][tech_name]*((100-tc[location_name][tech_name]['refund']['rate'])/100)
                else:
                    yearly_refund = results_pp[location_name]['I0'][tech_name]*tc[location_name][tech_name]['refund']['rate']/100 / tc[location_name][tech_name]['refund']['years'] # yearly refund [€]
                    refunds = np.zeros(economic_data['investment years']) # array initialise
                    refunds[:min(economic_data['investment years'],tc[location_name][tech_name]['refund']['years'])] = yearly_refund # array repeat yearly refund 
                    results_pp[location_name]['CF']['Refund'] += refunds # add refund to Cash Flow
                    lcoh[location_name]['Opex'][tech_name] -= refunds # add refund to Opex expenditures
                
                results_pp[location_name]['CF']['Tot'] += - results_pp[location_name]['CF']['Refund']
                
    # energy sold and purchased in study case 
    for carrier in production[location_name]:                           # for each carrier (electricity, hydrogen, gas, heat)
        
        if carrier+' grid' in consumption[location_name][carrier]:  # in the hypotesis of having all grids interacting with hydrogen chain
            
            if type(economic_data[carrier]['sale']) == str: # if the price series is given
                sale_serie = pd.read_csv(path+'/energy_price/'+economic_data[carrier]['sale'])['0'].to_numpy()
                if len(sale_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    sale_serie = np.tile(sale_serie,int(c.simulation_years))                   
                sold = consumption[location_name][carrier][carrier+' grid']['Tot'] * sale_serie
            else: # if the price is always the same 
                sold = consumption[location_name][carrier][carrier+' grid']['Tot'] * economic_data[carrier]['sale'] 
           
            sold = np.tile(sold,years_factor)
            sold = np.reshape(sold,(-1,8760))
            results_pp[location_name]['CF']['Sale'][carrier]   = sold.sum(axis=1)
            lcoh[location_name]['Opex'][carrier +' sold']   =  - sold.sum(axis=1) 
            
        purchase = {}                     
        if carrier+' grid' in production[location_name][carrier]:  # Now it must be considered that not all electricity or water or hydrogen is purchased for the hydrogen chain
            purchase[carrier] = np.zeros(8760*c.simulation_years)
            for tech_name in production[location_name][carrier][carrier+' grid']:
                if tech_name not in [carrier+' demand','Tot','fuel cell']:
                    purchase[carrier] += production[location_name][carrier][carrier+' grid'][tech_name]
            if type(economic_data[carrier]['purchase']) == str: # if the price series is given
                purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data[carrier]['purchase'])['0'].to_numpy()
                if len(purchase_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                         
                purchase = purchase[carrier] * purchase_serie
            else: # if the price is always the same 
                purchase = purchase[carrier] * economic_data[carrier]['purchase']
           
            purchase = np.tile(purchase,years_factor)
            purchase = np.reshape(purchase,(-1,8760))
            results_pp[location_name]['CF']['Purchase'][carrier]   = - purchase.sum(axis=1)
            lcoh[location_name]['Opex'][carrier +' purchased']  =   purchase.sum(axis=1) 
      
            if carrier == 'electricity':    # Electricity purchased even by PV and wind if not owned
                if 'wind' in structure[location_name] and structure[location_name]['wind']['owned'] == False:
                    purchase_wind = np.zeros(8760*c.simulation_years)
                    for tech_name in production[location_name][carrier]['wind']:
                        if tech_name not in [carrier+' demand',carrier+' grid','Tot','fuel cell']:
                            purchase_wind += production[location_name][carrier]['wind'][tech_name]
                    if type(economic_data['wind electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['wind electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                                             
                        purchase = purchase_wind * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_wind * economic_data['wind electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results_pp[location_name]['CF']['Purchase'][carrier]   += - purchase.sum(axis=1)
                    lcoh[location_name]['Opex']['wind electricity purchased']  =  purchase.sum(axis=1) 
                             
                                    
                if 'PV' in structure[location_name] and structure[location_name]['PV']['owned'] == False:
                    purchase_PV = np.zeros(8760*c.simulation_years)
                    for tech_name in production[location_name][carrier]['PV']:
                        if tech_name not in [carrier+' demand',carrier+' grid','Tot','fuel cell']:
                            purchase_PV += production[location_name][carrier]['PV'][tech_name]
                    if type(economic_data['pv electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['pv electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                              
                        purchase = purchase_PV * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_PV * economic_data['pv electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results_pp[location_name]['CF']['Purchase'][carrier] += - purchase.sum(axis=1)
                    lcoh[location_name]['Opex']['pv electricity purchased']  =  purchase.sum(axis=1)
                  
    # CF update considering inflation for each carrier
    for carrier in economic_data['inflation rate']:
        f = economic_data['inflation rate'][carrier]
        
        if carrier in results_pp[location_name]['CF']['Purchase']:
            for y in range(economic_data['investment years']):
                results_pp[location_name]['CF']['Purchase'][carrier][y] = results_pp[location_name]['CF']['Purchase'][carrier][y]*(1+f)**y
                
        if carrier in results_pp[location_name]['CF']['Sale']:
            for y in range(economic_data['investment years']):
                results_pp[location_name]['CF']['Sale'][carrier][y] = results_pp[location_name]['CF']['Sale'][carrier][y]*(1+f)**y
    
        for k in lcoh[location_name]['Opex']: 
            if carrier in k:
                for y in range(economic_data['investment years']):
                    lcoh[location_name]['Opex'][k][y] = lcoh[location_name]['Opex'][k][y]*(1+f)**y
                    
    # Building Cash Flow final array while changing sign to revenews and expenditures as needed in LCOH formula
    for carrier in results_pp[location_name]['CF']['Purchase']:
        results_pp[location_name]['CF']['Tot'] -= results_pp[location_name]['CF']['Purchase'][carrier]
        
    if revenues:        # if revenues have to be included in LCOH calculation
        for carrier in results_pp[location_name]['CF']['Sale']:
            if carrier in revenues:
                results_pp[location_name]['CF']['Tot'] -= results_pp[location_name]['CF']['Sale'][carrier]
        # lcoh dictionary
        keys_to_remove = []
        for carrier in list(lcoh[location_name]['Opex'].keys()):
            if 'sold' in carrier and not any(word in revenues for word in carrier.split()):  # deleting revenues array not included in the analysis
                keys_to_remove.append(carrier)
        for key in keys_to_remove:
            lcoh[location_name]['Opex'].pop(key)
    else:
        keys_to_remove = []
        for carrier in lcoh[location_name]['Opex']:
            if 'sold' in carrier:
                keys_to_remove.append(carrier)
        for key in keys_to_remove:
                del lcoh[location_name]['Opex'][key]   
                            
    results_pp[location_name]['CF']['Tot'] +=  - results_pp[location_name]['CF']['OeM']       
                                        
    # calculate I0
    results_pp[location_name]['I0']['Tot'] = 0
    for tech_name in results_pp[location_name]['I0']:
        if tech_name != 'Tot':
            results_pp[location_name]['I0']['Tot'] += results_pp[location_name]['I0'][tech_name]   
            
    for key in lcoh[location_name]['Opex']:
        lcoh[location_name]['Opex'][key] = np.insert(lcoh[location_name]['Opex'][key], 0, 0) # shifting Opex value to year 1 while only Capex is considered in year 0.
        
    lcoh[location_name]['Capex']['Total'] = sum(lcoh[location_name]['Capex'].values())  # Adding Capex total values to dictionary
    lcoh[location_name]['Opex']['Total'] = sum(lcoh[location_name]['Opex'].values())    # Adding Opex total values to dictionary
   
    # LCOH calculation
    
    # Hydrogen produced each year via electrolysis
    produced_hydrogen = [0] + [(sum(production[location_name]['hydrogen']['electrolyzer']['Tot']))/c.simulation_years]*economic_data['investment years']  # [kg/y] - No H2 produced in period 0
    r       = economic_data['interest rate']                    # [%] interest rate 
    I0      = results_pp[location_name]['I0']['Tot']            # [€] Initial investment at time = 0
    CF      = np.zeros(economic_data['investment years'] +1)    # Creating an empty array of year_factor + 1 dimension for Cash Flows in order to insert only I0 as first element
    CF[1:]  = results_pp[location_name]['CF']['Tot'].copy()     # [€] Cash Flows
    CF[0]   = I0
    if economic_data['decommissioning'] > 0:
        CF = np.append(CF, I0*economic_data['decommissioning'])
        produced_hydrogen.append(0)
        lcoh[location_name]['Capex']['Total'] = np.append(lcoh[location_name]['Capex']['Total'], I0*economic_data['decommissioning'])
        
    num=[]  # numerator
    den=[]  # denominator
    
    for i in range(len(CF)):

        num.append((CF[i])*(1/(1+r)**i))
        den.append(produced_hydrogen[i]*(1/(1+r)**i))
    
    LCOH = round(sum(num)/sum(den),3)
    # LCOH = sum(num)/sum(den)                          
    
    results_pp[location_name]['LCOH'] = {'Value [€/kgH2]'          : LCOH,
                                         'Discounted Expenditures' : num,
                                         'Discounted Production'   : den}
            
    for key in lcoh[location_name]['Opex']:
        for i in range(len(lcoh[location_name]['Opex'][key])):
            lcoh[location_name]['Opex'][key][i] = lcoh[location_name]['Opex'][key][i]*(1/(1+r)**i)
    
    for key in lcoh[location_name]['Capex']:
        for i in range(len(lcoh[location_name]['Capex'][key])):
            lcoh[location_name]['Capex'][key][i] = lcoh[location_name]['Capex'][key][i]*(1/(1+r)**i)
    
    # specific costs associated with each technology. Data handling.
    capex   = {}
    opex    = {}
    
    for key, value in lcoh[location_name]['Capex'].items():
        capex[key] = np.sum(value)
    for key, value in lcoh[location_name]['Opex'].items():
        opex[key] = np.sum(value)
        
    hydrogen_prod = sum(den)   # actualized hydrogen production

    # Building DataFrame for data visualization      
    df = pd.DataFrame([capex, opex], index=['Capex', 'Opex'])
    df = df.fillna(0)
    df = df.reindex(columns=[col for col in df.columns if col != 'Total'] + ['Total'])  # index 'Total' must be the last of the column
     
    
    df1 = df.copy()
    df1 = df1/hydrogen_prod
    df1 = df1.round(4)
    df1 = df1.drop(columns=df1.columns[(df1.loc['Capex'] == 0) & (df1.loc['Opex'] == 0)])    # removing elements not contributing to final LCOH value
    
    if plot == True:
      
        if revenues:
            for key in df.loc['Opex'].index.tolist():
                if key.replace(' sold', '') in revenues and 'sold' in key:
                    df.loc['Opex']['Total'] -= df.loc['Opex'][key]
        
        df = df.drop(columns=df.columns[(df.loc['Capex'] == 0) & (df.loc['Opex'] == 0)])    # removing elements not contributing to final LCOH value
        df = df.drop(columns=[col for col in df.columns if 'sold' in col])
        df = df/hydrogen_prod
        df = df.round(4)
  
        colors = ['#0e4d92', '#2380b2', '#5da5c5', '#9cc2a5', '#c8e0a1', '#ebd279', '#e18b4f', '#ff0000', '#00ff00', '#0000ff']
        colors1 = ['#7fcdbb', '#edf8b1']       
 
        labels_capex    = [col for col in df.columns if col != 'Total' and df.loc['Capex', col] != 0]
        labels_opex     = [col for col in df.columns if col != 'Total' and df.loc['Opex', col] != 0]
        labels_outer    = labels_capex + labels_opex

        values_capex = df.loc['Capex', labels_capex].tolist()
        values_opex = df.loc['Opex', labels_opex].tolist()
        values_outer = values_capex + values_opex

        repeated_labels = [label for label in labels_outer if labels_outer.count(label) > 1]

        label_colors = dict(zip(repeated_labels, colors[:len(repeated_labels)]))
        label_colors = {label: colors.pop(0) if label not in label_colors else label_colors[label] for label in labels_outer}
        
        labels_inner = ['Capex','Opex']
        values_inner = [df.loc['Capex','Total'],df.loc['Opex','Total']]
                
        # Data to plot
        explode = [0.] * len(labels_outer)
        explode1 = [0.] * len(labels_inner)
                                  
        #Plot
        plt.figure(dpi=300)
        plt.pie(values_outer, 
                labels=labels_outer, 
                startangle=180,
                frame=True,
                radius=5,
                colors=[label_colors[label] for label in labels_outer],
                explode = explode, 
                wedgeprops={'linewidth': 1, 'edgecolor': 'black'},
                autopct='%1.1f%%',
                pctdistance=1.15,
                labeldistance=1.32,
                textprops={'fontsize': 8})

        prop = fm.FontProperties(weight='bold')
        plt.pie(values_inner,
                labels=labels_inner,
                startangle=180, 
                radius=3.5,
                colors = colors1,
                explode=explode1,
                autopct='%1.1f%%',
                labeldistance=0.04,
                pctdistance=0.82,
                textprops={'fontproperties': prop, 'fontsize':9} )
        
        #Draw circle
        centre_circle = plt.Circle((0,0),1.75,color='black', fc='white',linewidth=0)
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
        column_labels = [label + " [€/kgH$_\mathregular{2}$]" for label in df.index]
        table = plt.table(cellText=df1.T.values,  
                  colLabels=column_labels,    
                  rowLabels=df1.columns,  
                  cellLoc='center',
                  loc='center',
                  bbox=[0.325, -1.25, 0.75, 0.8])  # table dimensions and position
        table.auto_set_font_size(True)
        table.scale(1, 1.)
        
        plt.suptitle(f'LCOH = {LCOH} €/kgH$_2$', y=0.05, fontsize=12, fontweight='bold', ha='center')
        plt.subplots_adjust(bottom=0.18)    

        plt.axis('equal')
        # plt.tight_layout()
        plt.show()        
    
    # saving results_pp in results/pkl
    with open(f"results/pkl/LCOH_assessment.pkl", 'wb') as f:  pickle.dump(results_pp,f)
    
    # saving results_pp in results/pkl
    
    results_to_csv = dict(results_pp)
    def dict_arrays_to_lists(d):
        for key, value in d.items():
            if isinstance(value, dict):
                d[key] = dict_arrays_to_lists(value)
            elif isinstance(value, np.ndarray):
                d[key] = value.tolist()
        return d
    
    results_to_csv = dict_arrays_to_lists(results_to_csv)
    
    #COMMENTO
    def max_item_length(d):
        max_ = 0
        for value in d.values():
            if isinstance(value, list):
                max_ = max(max_, len(value))
            elif isinstance(value, dict):
                max_ = max(max_, max_item_length(value))
        return max_

    max_length = max_item_length(results_to_csv)
    
    for i in results_to_csv.keys():
        for j in results_to_csv[i].keys():
            for k in results_to_csv[i][j].keys():
                if isinstance(results_to_csv[i][j][k], list):
                    a = results_to_csv[i][j][k]
                    results_to_csv[i][j][k] = {None:a}
                elif isinstance(results_to_csv[i][j][k], (int,float)):
                    a = [results_to_csv[i][j][k]] + [0]*(max_length-1)
                    results_to_csv[i][j][k] = {None:a}
    
    data = {(i, j, k, l): results_to_csv[i][j][k][l]
                                  if isinstance(results_to_csv[i][j][k][l], (int, str))
                                  else np.array(results_to_csv[i][j][k][l])
                                  for i in results_to_csv.keys()
                                  for j in results_to_csv[i].keys()
                                  for k in results_to_csv[i][j].keys()
                                  for l in results_to_csv[i][j][k].keys()}
    
    df_ = pd.DataFrame.from_dict(data,orient='index')

    df_.index = pd.MultiIndex.from_tuples(df_.index, names=['level_1', 'level_2', 'level_3', 'values'])
    df_ = df_.transpose()
    df_.to_csv('results/csv/LCOH_assessment.csv',index=False,sep=';',decimal=',')
    
    if print_ == True:
        print("\nThe LCOH calculated for the considered scenario for "+location_name+" location results in "+str(LCOH)+" €/kgH2")
    
    return(LCOH)                                      
                

def LCOE (location_name,
         structure,
         name_studycase,
         economic_data,
         path,
         revenues = False,
         refund = False,
         plot = False,
         print_ = False):
    
    """
    Levelized Cost of Electricity Calculation
    -------------
    location_name: str - location_name
    
    structure: dict - studycase
    
    name_studycase: str name of study case results file.pkl
                      
                                                                                                                                              

         

                                                                                                   

    economic_data: dictionary
    'REC': dictionary REC economic parameters definition
        'collective self consumption incentives': [€/kWh]
        'incentives redistribution': 0-100 how the incentives are redistributed between prosumers, consumers and REC manger
    'carrier_name': dictionary (repeat for reach considered carrier: electricity, hydrogen, gas)
        'purchase': [€/kWh] electricity, [€/Sm^3] gas and [€/kg] hydrogen
        'sales': [€/kWh] electricity, [€/Sm^3] gas and [€/kg] hydrogen
    'interest rate': 0-1 [rate/year]
    'inflation rate': -1-1 [rate/year] cost evolution of each carrier
    'decommissioning': 0-1 [-] system dismantling as a % of initial construction costs (Total CAPEX)
    'investment year': time horizon for which to evaluate the economic analysis (must be a multiple of simulation_year in general.json)
     
    path: str path of the input data folder 
    
    revenues: list/tuple of str/bool defining if generated revenues from excess energy streams have to be included in the calculation. In case the carrier name(s) is/are specified. Default = False
                                                                      
         
                                                              
    
    refund: boolean value defining refund cash flows have to be included in the calculation. Default = False
                                                                          
         
                                                                
    
    VALCOE: boolean, put True if you want to calculate the Value-Adjusted Levelized Cost of Electricity
                    
    output:  [€/kWh] float value of LCOE for the considered configuration
    """
    
    technologies_of_interest = ['PV', 'wind', 'fuel cell']
    present_technologies = []

    for tech_name in structure[location_name]:
        if tech_name in technologies_of_interest:
            present_technologies.append(tech_name)

    if present_technologies:
        tech_string = ', '.join(present_technologies)
        print(f"\nWarning: The LCOE takes into account at the numerator all the technologies and cash flows employed in the system: in this case electricity produced by {tech_string} is taken into consideration at the denominator")
    else:
        raise ValueError("Error: None of the specified technologies (PV, wind, fuel cell) are present in the system. Include at least one of them to calculate LCOE.")


    years_factor = int(economic_data['investment years'] / c.simulation_years) # this factor is useful to match the length of the energy simulation with the length of the economic investment
    
    if economic_data['investment years'] % c.simulation_years != 0:
        raise ValueError(f"'simulation_years' has been set equal to {c.simulation_years} in general.py but the 'investement_years' has been set equal to {economic_data['investment years']} in energy_market.py. This is not correct because simulation_years must be a submultiple of investement_years.")
        
    # open cost of componenets of studycase
    with open('results/pkl/tech_cost_'+name_studycase+'.pkl', 'rb') as f:       tc = pickle.load(f)   
    
    # check for hydrogen carrier to be included in location balances
    with open('results/pkl/consumption_'+name_studycase+'.pkl', 'rb')           as f: consumption  = pickle.load(f) 
    with open('results/pkl/production_'+name_studycase+'.pkl', 'rb')           as f: production  = pickle.load(f)

                
    # check for electricity carrier to be included in location balances
    if 'wind' in structure[location_name] or 'PV' in structure[location_name] or 'fuel cell' in structure[location_name]:
        pass
    else:
        print("\nElectricity carrier not included in "+location_name+" location - LCOE calculation not available")
        return 
                                 

    # check energy balances timestep and transforms the series into hourly values because the energy price is always given either on a hourly basis (electricity) or per unit of mass (gas and hydrogen)
    if c.timestep != 60:
        # Number of steps per hour based on the timestep
        steps_per_hour = 60 // c.timestep          
        # Iterate over the electricity consumption dictionary
        for carrier in consumption[location_name]:
            for tech_name in consumption[location_name][carrier]:
                for tech_name1 in consumption[location_name][carrier][tech_name]:
                    consumption[location_name][carrier][tech_name][tech_name1] = consumption[location_name][carrier][tech_name][tech_name1].reshape(-1, steps_per_hour).sum(axis=1)*(c.timestep/60)
        # Iterate over the electricity production dictionary
        for carrier in production[location_name]:
            for tech_name in production[location_name][carrier]:
                for tech_name1 in production[location_name][carrier][tech_name]:
                    production[location_name][carrier][tech_name][tech_name1] = production[location_name][carrier][tech_name][tech_name1].reshape(-1, steps_per_hour).sum(axis=1)*(c.timestep/60)

    # balances are now in the form of yearly arrays of 8760 values. Converting energy carriers and material streams expressed as mass flow rates into hourly values necessary for economic analysis purposes. kg/s to kg/h and Sm^3/s to Sm^3/h
    for carrier in consumption[location_name]:
        if carrier in ['hydrogen','LP hydrogen','HP hydrogen','oxygen','process steam','gas','water']:
            for tech_name in consumption[location_name][carrier]:
                for tech_name1 in consumption[location_name][carrier][tech_name]:
                    consumption[location_name][carrier][tech_name][tech_name1] = consumption[location_name][carrier][tech_name][tech_name1]*3600
    
    for carrier in production[location_name]:
        if carrier in ['hydrogen','LP hydrogen','HP hydrogen','oxygen','process steam','gas','water']:
            for tech_name in production[location_name][carrier]:
                for tech_name1 in production[location_name][carrier][tech_name]:
                    production[location_name][carrier][tech_name][tech_name1] = production[location_name][carrier][tech_name][tech_name1]*3600

 
    results_pp  = {}    # dictionary initialising global lcoe results of each location
    lcoe        = {}    # dictionary initialising specific lcoe results of each location
        
    results_pp[location_name]   = {}    # dictionary initialising economic results_pp
    lcoe[location_name]         = {}    # dictionary initialising economic results_pp
    
    # initialise cash flow:     
    results_pp[location_name]['CF'] = {'OeM'        : np.zeros(economic_data['investment years']),
                                       'Purchase'   : {},
                                       'Sale'       : {},
                                       'Refund'     : np.zeros(economic_data['investment years']),
                                       'Tot'        : np.zeros(economic_data['investment years'])} 
 
    results_pp[location_name]['I0'] = {} # initialise initial investment
    
    lcoe[location_name]['Capex']    = {}
    lcoe[location_name]['Opex']     = {}
    
    for tech_name in tc[location_name]:              # considering each technology in the location
 
        results_pp[location_name]['I0'][tech_name] = tc[location_name][tech_name]['total cost'] # I0   
        results_pp[location_name]['CF']['OeM'][:] += - tc[location_name][tech_name]['OeM'] # OeM
        
        lcoe[location_name]['Capex'][tech_name] = np.concatenate(([tc[location_name][tech_name]['total cost']], np.full(economic_data['investment years'], 0))) # Capex array
        lcoe[location_name]['Opex'][tech_name]  = np.repeat(tc[location_name][tech_name]['OeM'],economic_data['investment years']) # Opex array  
        
        # replacements 
        if tc[location_name][tech_name]['replacement']['years'] == "ageing": # if replacement year is calculated according to ageing
            with open('results/pkl/ageing_'+name_studycase+'.pkl', 'rb') as f:
                age = pickle.load(f)     
                age = age[location_name][tech_name][0]
                for a in age:
                    rep_time = int(a/8760)
                    results_pp[location_name]['CF']['OeM'][rep_time] += - results_pp[location_name]['I0'][tech_name] * tc[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
                    lcoe[location_name]['Capex'][tech_name] += lcoe[location_name]['Capex'][tech_name] * tc[location_name][tech_name]['replacement']['rate']/100 # subtract technology replacement to location Cash Flow
        else: # if replacement time is given
            rep_time = tc[location_name][tech_name]['replacement']['years']
            while rep_time < economic_data['investment years']: # if tech_name replacement happens before the end of the simulation
                results_pp[location_name]['CF']['OeM'][rep_time-1] += - np.float64(results_pp[location_name]['I0'][tech_name])*np.float64(tc[location_name][tech_name]['replacement']['rate'])/np.float64(100) # subtract technology replacement to location Cash Flow. -1 subtracted to index because the array is shifted of 1 position during LCOH calculation -> CF[1:]  = results_pp[location_name]['CF']['Tot'].copy()    # [€] Cash Flows
                lcoe[location_name]['Capex'][tech_name][rep_time] += np.float64(lcoe[location_name]['Capex'][tech_name][0])*np.float64(tc[location_name][tech_name]['replacement']['rate'])/np.float64(100) # subtract technology replacement to location Cash Flow. np.float type added to avoid overflow problems 
                rep_time += tc[location_name][tech_name]['replacement']['years']
        
        if refund: # if refund has to be included in LCOE calculation
                
            if tc[location_name][tech_name]['refund']['years'] == 0 and tc[location_name][tech_name]['refund']['rate'] == 0:  # no refunds considered
                pass
            elif tc[location_name][tech_name]['refund']['years'] == 0 and tc[location_name][tech_name]['refund']['rate'] != 0:
                results_pp[location_name]['I0'][tech_name] = results_pp[location_name]['I0'][tech_name]*((100-tc[location_name][tech_name]['refund']['rate'])/100)
                lcoe[location_name]['Capex'][tech_name] = lcoe[location_name]['Capex'][tech_name]*((100-tc[location_name][tech_name]['refund']['rate'])/100)
            else:
                yearly_refund = results_pp[location_name]['I0'][tech_name]*tc[location_name][tech_name]['refund']['rate']/100 / tc[location_name][tech_name]['refund']['years'] # yearly refund [€]
                refunds = np.zeros(economic_data['investment years']) # array initialise
                refunds[:min(economic_data['investment years'],tc[location_name][tech_name]['refund']['years'])] = yearly_refund # array repeat yearly refund 
                results_pp[location_name]['CF']['Refund'] += refunds # add refund to Cash Flow
                lcoe[location_name]['Opex'][tech_name] -= refunds # add refund to Opex expenditures
            
            results_pp[location_name]['CF']['Tot'] += - results_pp[location_name]['CF']['Refund']
      

    # energy sold and purchased in study case 
    for carrier in production[location_name]:                           # for each carrier (electricity, hydrogen, gas, heat)
        
        if carrier+' grid' in consumption[location_name][carrier]:  

            if type(economic_data[carrier]['sale']) == str: # if the price series is given
                sale_serie = pd.read_csv(path+'/energy_price/'+economic_data[carrier]['sale'])['0'].to_numpy()
                if len(sale_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    sale_serie = np.tile(sale_serie,int(c.simulation_years))                   
                sold = consumption[location_name][carrier][carrier+' grid']['Tot'] * sale_serie
            else: # if the price is always the same 
                sold = consumption[location_name][carrier][carrier+' grid']['Tot'] * economic_data[carrier]['sale'] 
           
            sold = np.tile(sold,years_factor)
            sold = np.reshape(sold,(-1,8760))
            results_pp[location_name]['CF']['Sale'][carrier] = sold.sum(axis=1)
            lcoe[location_name]['Opex'][carrier +' sold'] = - sold.sum(axis=1) 
        
        purchase = {}
        if carrier+' grid' in production[location_name][carrier]:
            purchase[carrier] = np.zeros(8760*c.simulation_years)
            for tech_name in production[location_name][carrier][carrier+' grid']:
                if tech_name not in ['Tot']:
                    purchase[carrier] += production[location_name][carrier][carrier+' grid'][tech_name]
                     
            if type(economic_data[carrier]['purchase']) == str: # if the price series is given
                purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data[carrier]['purchase'])['0'].to_numpy()
                if len(purchase_serie) < 8762: #It means that the serie must be repeated for the simulation_length selected
                    purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                         
                purchase = purchase[carrier] * purchase_serie
            else: # if the price is always the same 
                purchase = purchase[carrier] * economic_data[carrier]['purchase']
           
            purchase = np.tile(purchase,years_factor)
            purchase = np.reshape(purchase,(-1,8760))
            results_pp[location_name]['CF']['Purchase'][carrier] = - purchase.sum(axis=1)
            lcoe[location_name]['Opex'][carrier +' purchased'] = purchase.sum(axis=1) 
      
            if carrier == 'electricity':    # Electricity purchased even by PV and wind if not owned
                if 'wind' in structure[location_name] and structure[location_name]['wind']['owned'] == False:
                    purchase_wind = np.zeros(8760*c.simulation_years)
                    for tech_name in production[location_name][carrier]['wind']:
                        if tech_name not in ['Tot']:    # I'm considering even the electricity injected from wind into grid because if not owned the electricity must be all purchased (PPA as produced contract)
                                                        # If we'll decide to add the PPA simultaneous with wind production, which means buying only the needed electricity (at a higher price of course) carrier + ' grid' should be added to 'Tot'
                            purchase_wind += production[location_name][carrier]['wind'][tech_name]
                    
                    if type(economic_data['wind electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['wind electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                              
                        purchase = purchase_wind * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_wind * economic_data['wind electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results_pp[location_name]['CF']['Purchase'][carrier] += - purchase.sum(axis=1)
                    lcoe[location_name]['Opex']['wind electricity purchased']  =  purchase.sum(axis=1)
                             
                if 'PV' in structure[location_name] and structure[location_name]['PV']['owned'] == False:
                    purchase_PV = np.zeros(8760*c.simulation_years)
                    for tech_name in production[location_name][carrier]['PV']:
                        if tech_name not in ['Tot']:    # I'm considering even the electricity injected from PV into grid because if not owned the electricity must be all purchased (PPA as produced contract)
                                                        # If we'll decide to add the PPA simultaneous with PV production contract, which means buying only the needed electricity (at a higher price of course) carrier + ' grid' should be added to 'Tot'                        
                            purchase_PV += production[location_name][carrier]['PV'][tech_name]
                    
                    if type(economic_data['pv electricity']['purchase']) == str: # if the price series is given
                        purchase_serie = pd.read_csv(path+'/energy_price/'+economic_data['pv electricity']['purchase'])['0'].to_numpy()
                        if len(purchase_serie) < 8762:
                            purchase_serie = np.tile(purchase_serie,int(c.simulation_years))                              
                        purchase = purchase_PV * purchase_serie
                    else: # if the price is always the same 
                        purchase = purchase_PV * economic_data['pv electricity']['purchase']
                   
                    purchase = np.tile(purchase,years_factor)
                    purchase = np.reshape(purchase,(-1,8760))
                    results_pp[location_name]['CF']['Purchase'][carrier] += - purchase.sum(axis=1)
                    lcoe[location_name]['Opex']['pv electricity purchased']  =  purchase.sum(axis=1)


    # CF update considering inflation for each carrier
    for carrier in economic_data['inflation rate']:
        f = economic_data['inflation rate'][carrier]
        
        if carrier in results_pp[location_name]['CF']['Purchase']:
            for y in range(economic_data['investment years']):
                results_pp[location_name]['CF']['Purchase'][carrier][y] = results_pp[location_name]['CF']['Purchase'][carrier][y]*(1+f)**y
                
        if carrier in results_pp[location_name]['CF']['Sale']:
            for y in range(economic_data['investment years']):
                results_pp[location_name]['CF']['Sale'][carrier][y] = results_pp[location_name]['CF']['Sale'][carrier][y]*(1+f)**y
    
        for k in lcoe[location_name]['Opex']: 
            if carrier in k:
                for y in range(economic_data['investment years']):
                    lcoe[location_name]['Opex'][k][y] = lcoe[location_name]['Opex'][k][y]*(1+f)**y
                    
    # Building Cash Flow final array while changing sign to revenews and expenditures as needed in LCOH formula
    for carrier in results_pp[location_name]['CF']['Purchase']:
        results_pp[location_name]['CF']['Tot'] -= results_pp[location_name]['CF']['Purchase'][carrier]
        
    if revenues:        # if revenues have to be included in LCOH calculation
        for carrier in results_pp[location_name]['CF']['Sale']:
            if carrier in revenues:
                results_pp[location_name]['CF']['Tot'] -= results_pp[location_name]['CF']['Sale'][carrier]
        # lcoh dictionary
        keys_to_remove = []
        for carrier in list(lcoe[location_name]['Opex'].keys()):
            if 'sold' in carrier and not any(word in revenues for word in carrier.split()):  # deleting revenues array not included in the analysis
                keys_to_remove.append(carrier)
        for key in keys_to_remove:
            lcoe[location_name]['Opex'].pop(key)
    else:
        keys_to_remove = []
        for carrier in lcoe[location_name]['Opex']:
            if 'sold' in carrier:
                keys_to_remove.append(carrier)
        for key in keys_to_remove:
                del lcoe[location_name]['Opex'][key]   
                            
    results_pp[location_name]['CF']['Tot'] +=  - results_pp[location_name]['CF']['OeM']       
                                        
    # calculate I0
    results_pp[location_name]['I0']['Tot'] = 0
    for tech_name in results_pp[location_name]['I0']:
        if tech_name != 'Tot':
            results_pp[location_name]['I0']['Tot'] += results_pp[location_name]['I0'][tech_name]   
            
    for key in lcoe[location_name]['Opex']:
        lcoe[location_name]['Opex'][key] = np.insert(lcoe[location_name]['Opex'][key], 0, 0) # shifting Opex value to year 1 while only Capex is considered in year 0.
        
    lcoe[location_name]['Capex']['Total'] = sum(lcoe[location_name]['Capex'].values())  # Adding Capex total values to dictionary
    lcoe[location_name]['Opex']['Total'] = sum(lcoe[location_name]['Opex'].values())    # Adding Opex total values to dictionary
   
    # LCOE calculation
    
    # Electricity produced each year 

    produced_electricity_pv, produced_electricity_wind, produced_electricity_fuelcell = [[],[],[]]

    if 'PV' in structure[location_name]:
        produced_electricity_pv = [0] + [(sum(production[location_name]['electricity']['PV']['Tot']))/c.simulation_years]*economic_data['investment years']  # [kWh/y] - No electricity produced in period 0
    if 'wind' in structure[location_name]:
        produced_electricity_wind = [0] + [(sum(production[location_name]['electricity']['wind']['Tot']))/c.simulation_years]*economic_data['investment years']  # [kWh/y] - No electricity produced in period 0
    if 'fuel cell' in structure[location_name]:
        produced_electricity_fuelcell = [0] + [(sum(production[location_name]['electricity']['fuel cell']['Tot']))/c.simulation_years]*economic_data['investment years']  # [kWh/y] - No electricity produced in period 0

    produced_electricity = produced_electricity_pv+produced_electricity_wind+produced_electricity_fuelcell
    
    r       = economic_data['interest rate']                    # [%] interest rate 
    I0      = results_pp[location_name]['I0']['Tot']            # [€] Initial investment at time = 0
    CF      = np.zeros(economic_data['investment years'] +1)    # Creating an empty array of year_factor + 1 dimension for Cash Flows in order to insert only I0 as first element
    CF[1:]  = results_pp[location_name]['CF']['Tot'].copy()     # [€] Cash Flows
    CF[0]   = I0
    if economic_data['decommissioning'] > 0:
        CF = np.append(CF, I0*economic_data['decommissioning'])
        produced_electricity.append(0)
        lcoe[location_name]['Capex']['Total'] = np.append(lcoe[location_name]['Capex']['Total'], I0*economic_data['decommissioning'])
        
    num=[]  # numerator
    den=[]  # denominator
    
    for i in range(len(CF)):
 
        num.append((CF[i])*(1/(1+r)**i))
        den.append(produced_electricity[i]*(1/(1+r)**i))
    
    LCOE = round(sum(num)/sum(den),3)
    # LCOE = sum(num)/sum(den)                          
    
    results_pp[location_name]['LCOE'] = {'Value [€/kgH2]'          : LCOE,
                                         'Discounted Expenditures' : num,
                                         'Discounted Production'   : den}
            
    for key in lcoe[location_name]['Opex']:
        for i in range(len(lcoe[location_name]['Opex'][key])):
            lcoe[location_name]['Opex'][key][i] = lcoe[location_name]['Opex'][key][i]*(1/(1+r)**i)
    
    for key in lcoe[location_name]['Capex']:
        for i in range(len(lcoe[location_name]['Capex'][key])):
            lcoe[location_name]['Capex'][key][i] = lcoe[location_name]['Capex'][key][i]*(1/(1+r)**i)
    
    # specific costs associated with each technology. Data handling.
    capex   = {}
    opex    = {}
    
    for key, value in lcoe[location_name]['Capex'].items():
        capex[key] = np.sum(value)
    for key, value in lcoe[location_name]['Opex'].items():
        opex[key] = np.sum(value)
        
    electricity_prod = sum(den)   # actualized electricity production
 
    # Building DataFrame for data visualization      
    df = pd.DataFrame([capex, opex], index=['Capex', 'Opex'])
    df = df.fillna(0)
    df = df.reindex(columns=[col for col in df.columns if col != 'Total'] + ['Total'])  # index 'Total' must be the last of the column
     
    
    df1 = df.copy()
    df1 = df1/electricity_prod
    df1 = df1.round(4)
    df1 = df1.drop(columns=df1.columns[(df1.loc['Capex'] == 0) & (df1.loc['Opex'] == 0)])    # removing elements not contributing to final LCOH value
    
    if plot == True:
      
        if revenues:
            for key in df.loc['Opex'].index.tolist():
                if key.replace(' sold', '') in revenues and 'sold' in key:
                    df.loc['Opex']['Total'] -= df.loc['Opex'][key]
        
        df = df.drop(columns=df.columns[(df.loc['Capex'] == 0) & (df.loc['Opex'] == 0)])    # removing elements not contributing to final LCOH value
        df = df.drop(columns=[col for col in df.columns if 'sold' in col])
        df = df/electricity_prod
        df = df.round(4)
  
        colors = ['#0e4d92', '#2380b2', '#5da5c5', '#9cc2a5', '#c8e0a1', '#ebd279', '#e18b4f', '#ff0000', '#00ff00', '#0000ff']
        colors1 = ['#7fcdbb', '#edf8b1']       
 
        labels_capex    = [col for col in df.columns if col != 'Total' and df.loc['Capex', col] != 0]
        labels_opex     = [col for col in df.columns if col != 'Total' and df.loc['Opex', col] != 0]
        labels_outer    = labels_capex + labels_opex
 
        values_capex = df.loc['Capex', labels_capex].tolist()
        values_opex = df.loc['Opex', labels_opex].tolist()
        values_outer = values_capex + values_opex
 
        repeated_labels = [label for label in labels_outer if labels_outer.count(label) > 1]
 
        label_colors = dict(zip(repeated_labels, colors[:len(repeated_labels)]))
        label_colors = {label: colors.pop(0) if label not in label_colors else label_colors[label] for label in labels_outer}
        
        labels_inner = ['Capex','Opex']
        values_inner = [df.loc['Capex','Total'],df.loc['Opex','Total']]
                
        # Data to plot
        explode = [0.] * len(labels_outer)
        explode1 = [0.] * len(labels_inner)
                                  
        #Plot
        plt.figure(dpi=300)
        plt.pie(values_outer, 
                labels=labels_outer, 
                startangle=180,
                frame=True,
                radius=5,
                colors=[label_colors[label] for label in labels_outer],
                explode = explode, 
                wedgeprops={'linewidth': 1, 'edgecolor': 'black'},
                autopct='%1.1f%%',
                pctdistance=1.15,
                labeldistance=1.32,
                textprops={'fontsize': 8})
 
        prop = fm.FontProperties(weight='bold')
        plt.pie(values_inner,
                labels=labels_inner,
                startangle=180, 
                radius=3.5,
                colors = colors1,
                explode=explode1,
                autopct='%1.1f%%',
                labeldistance=0.04,
                pctdistance=0.82,
                textprops={'fontproperties': prop, 'fontsize':9} )
        
        #Draw circle
        centre_circle = plt.Circle((0,0),1.75,color='black', fc='white',linewidth=0)
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
        column_labels = [label + " [€/kWh]" for label in df.index]
        table = plt.table(cellText=df1.T.values,  
                  colLabels=column_labels,    
                  rowLabels=df1.columns,  
                  cellLoc='center',
                  loc='center',
                  bbox=[0.325, -1.25, 0.75, 0.8])  # table dimensions and position
        table.auto_set_font_size(True)
        table.scale(1, 1.)
        
        plt.suptitle(f'LCOE = {LCOE} €/kWh', y=0.05, fontsize=12, fontweight='bold', ha='center')
        plt.subplots_adjust(bottom=0.18)    
 
        plt.axis('equal')
        # plt.tight_layout()
        plt.show()        
    
    # saving results_pp in results/pkl
    with open(f"results/pkl/LCOE_assessment.pkl", 'wb') as f:  pickle.dump(results_pp,f)
    
    # saving results_pp in results/pkl
    
    results_to_csv = dict(results_pp)
    def dict_arrays_to_lists(d):
        for key, value in d.items():
            if isinstance(value, dict):
                d[key] = dict_arrays_to_lists(value)
            elif isinstance(value, np.ndarray):
                d[key] = value.tolist()
        return d
    
    results_to_csv = dict_arrays_to_lists(results_to_csv)
    
    #COMMENTO
    def max_item_length(d):
        max_ = 0
        for value in d.values():
            if isinstance(value, list):
                max_ = max(max_, len(value))
            elif isinstance(value, dict):
                max_ = max(max_, max_item_length(value))
        return max_
 
    max_length = max_item_length(results_to_csv)
    
    for i in results_to_csv.keys():
        for j in results_to_csv[i].keys():
            for k in results_to_csv[i][j].keys():
                if isinstance(results_to_csv[i][j][k], list):
                    a = results_to_csv[i][j][k]
                    results_to_csv[i][j][k] = {None:a}
                elif isinstance(results_to_csv[i][j][k], (int,float)):
                    a = [results_to_csv[i][j][k]] + [0]*(max_length-1)
                    results_to_csv[i][j][k] = {None:a}
    
    data = {(i, j, k, l): results_to_csv[i][j][k][l]
                                  if isinstance(results_to_csv[i][j][k][l], (int, str))
                                  else np.array(results_to_csv[i][j][k][l])
                                  for i in results_to_csv.keys()
                                  for j in results_to_csv[i].keys()
                                  for k in results_to_csv[i][j].keys()
                                  for l in results_to_csv[i][j][k].keys()}
    
    df_ = pd.DataFrame.from_dict(data,orient='index')
 
    df_.index = pd.MultiIndex.from_tuples(df_.index, names=['level_1', 'level_2', 'level_3', 'values'])
    df_ = df_.transpose()
    df_.to_csv('results/csv/LCOE_assessment.csv',index=False,sep=';',decimal=',')
    
    if print_ == True:
        print("\nThe LCOE calculated for the considered scenario for "+location_name+" location results in "+str(LCOE)+" €/kWh")

    return(LCOE)   
