'''
This is a class object to store extra info about each site-product.

Created 2018-07-22 by Greg Plank
'''


import sys
sys.path.append("C:\Python26\SCG_64\Lib")
import sim_server
import datetime


low, med, high = 2, 5, 8
debug_obj = sim_server.Debug()
model_obj = sim_server.Model()

class Site_Product_Info(object):
    def __init__(self, name):
        self.name = name
        self.lead_time = 0.0
        self.minimum_order_qty = 0.0
        self.order_lot_size = 0.0
        self.inventory_reviewed = datetime.datetime(1970, 1, 1, 0, 0, 0)
        self.future_inventory_position = 0.0
        self.future_daily_sales = 0.0
        self.future_order_quantity = 0.0
        self.future_forecast = 0.0
        self.min_order_used = False
        self.vendor_order_minimum = 0.0
        self.lead_time_demand = 0.0
