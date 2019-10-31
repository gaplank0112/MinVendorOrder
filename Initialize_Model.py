'''
This script ia an On Model Begin script
This script initializes extra ordering information from the site sourcing table
The lead time input is in the Transportation Policies table under the Guaranteed Service Time field.
It should be in days and should NOT have a time unit.
The vendor minimum quantity is in the Site Sourcing Policies table under the Policy Parameter field.
It should be in units and should NOT have any units definitions attached.
All extra data is stored in a custom attribute either on the site-product object or the model object.

Created 2018-07-22 by Greg Plank
'''


import sys
import sim_server
from csv import reader
from SiteProductInfo import Site_Product_Info
sys.path.append("C:\\Python26\\SCG_64\\Lib")

low, med, high = 2, 5, 8
debug_obj = sim_server.Debug()
model_obj = sim_server.Model()


def main():
    debug_obj.trace(low, "-" * 20)
    debug_obj.trace(low, "Initialize model called at " + sim_server.NowAsString())

    set_vendor_order_details()
    set_vendor_product_list()
    set_vendor_lead_times()
    set_dos_output()
    set_vendor_min_output()


def set_vendor_order_details():
    debug_obj.trace(med, "  Setting extra site product info")
    filename = "siteproductsource.dat"

    datafile = model_obj.modelpath + '\\' + filename
    t = open(datafile)
    csv_t = reader(t, delimiter='\t')
    header = csv_t.next()
    for row in csv_t:
        debug_obj.trace(high, str(row))

        product_name = get_str_element(row, 2)
        debug_obj.trace(low, "HERE %s" % product_name)
        site_name = get_str_element(row, 1)
        debug_obj.trace(low, "HERE %s" % site_name)
        vendor_minimum_quantity = get_float_element(row, 5)
        debug_obj.trace(low, "HERE %s" % vendor_minimum_quantity)
        minimum_order_qty = get_float_element(row, 12)
        debug_obj.trace(low, "HERE %s" % minimum_order_qty)
        order_lot_size = get_float_element(row, 13)
        debug_obj.trace(low, "HERE %s" % order_lot_size)

        site_obj = sim_server.Site(site_name)
        site_product_obj = site_obj.getsiteproduct(product_name)
        site_product_name = site_name + '_' + product_name
        site_product_info = Site_Product_Info(site_product_name)
        site_product_info.minimum_order_qty = minimum_order_qty
        site_product_info.order_lot_size = order_lot_size
        site_product_info.vendor_order_minimum = vendor_minimum_quantity
        site_product_obj.setcustomattribute("SiteProductInfo", site_product_info)


def set_vendor_product_list():
    debug_obj.trace(med, "  Setting site-vendor-product dictionary")
    site_vendor_products_dict = {}
    for site_obj in model_obj.sites:
        debug_obj.trace(high,'   Site - %s' % site_obj.name)
        for sp_obj in site_obj.products:
            debug_obj.trace(high,'   Product - %s' % sp_obj.product.name)
            if len(sp_obj.sources) > 1:
                debug_obj.logerror("Model initialization: Too many sources for product %s at site %s. Only one"
                                   "source allowed." % (sp_obj.product.name, site_obj.name))
                continue
            # Add this site - vendor - list of products dictionary for the model object.
            try:
                source_name = sp_obj.sources[0].name
            except:
                #we skip items with no source
                continue
            product_name = sp_obj.product.name
            debug_obj.trace(low, "    Add to site-vendor-product dictionary %s %s %s" % (site_obj.name,source_name,
                                                                                       product_name))
            try:
                s1 = site_vendor_products_dict[site_obj.name]
            except:
                site_vendor_products_dict[site_obj.name] = {}
                s1 = site_vendor_products_dict[site_obj.name]
            try:
                s2 = site_vendor_products_dict[site_obj.name][source_name]
            except:
                site_vendor_products_dict[site_obj.name][source_name] = []
                s2 = site_vendor_products_dict[site_obj.name][source_name]
            if product_name not in s2:
                site_vendor_products_dict[site_obj.name][source_name].append(product_name)

    model_obj.setcustomattribute("SiteVendorProductDictionary", site_vendor_products_dict)

    debug_obj.trace(high,"##### site_vendor_products_dict ####")
    debug_obj.trace(high, str(site_vendor_products_dict))
    debug_obj.trace(high,"##################################")


def set_vendor_lead_times():
    debug_obj.trace(med,"  Setting lead times")
    filename = "siteproduct.dat"

    datafile = model_obj.modelpath + '\\' + filename
    t = open(datafile)
    csv_t = reader(t, delimiter='\t')
    header = csv_t.next()
    for row in csv_t:
        debug_obj.trace(high, str(row))

        if row[16] != "":
            product_name = get_str_element(row, 2)
            debug_obj.trace(low, "HERE %s" % product_name)
            site_name = get_str_element(row, 1)
            debug_obj.trace(low, "HERE %s" % site_name)
            lead_time = get_str_element(row, 16)
            debug_obj.trace(low, "HERE %s" % lead_time)
            debug_obj.trace(low, "%s %s %s "% (site_name, product_name, lead_time ))
            lead_time = float(check_lead_time(lead_time, site_name, product_name))
            site_obj = sim_server.Site(site_name)
            site_product_obj = site_obj.getsiteproduct(product_name)
            sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
            sp_info.lead_time = lead_time


def check_lead_time(val,site_name, product_name):  # This checks for time units in the input (i.e. 20 DAY or 48 HR).
    # Get rid of this when we build the ability
    for i in val:
        if i.isalpha():
            debug_obj.logerror("At this time, lead time must be a numeric value in days - no time unit allowed")
            debug_obj.logerror("Setting lead time to 1.0 days for site %s and product %s." % (site_name, product_name))
            return 1.0
    return val

def set_dos_output():
    debug_obj.trace(0,'scenarioid, currentreplication, current_date, site_name, '
                      'product_name, on_hand_inventory, due_in_quantity, due_out_quantity, lead_time,'
                      'lead_time_demand, daily_sales,current_DOS, future_inventory_position, future_forecast,'
                      'future_daily_sales, future_DOS', 'inventory_position.txt')


def set_vendor_min_output():
    debug_obj.trace(0,'scenario_id,replication,destination,vendor,product,vendor_min,safety_DOS,'
                      'occupancy_cost', 'vendor_mins.txt')
    scenario_id = model_obj.scenarioid
    rep_num = model_obj.currentreplication
    for site_obj in model_obj.sites:
        if site_obj.name[0] == 'W':
            for site_product_obj in site_obj.products:
                vendor = site_product_obj.sources[0]
                safety_stock = site_product_obj.reorderptDOS
                sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
                vendor_min = sp_info.vendor_order_minimum
                debug_obj.trace(0,'%s,%s,%s,%s,%s,%s,%s,%s' % (scenario_id, rep_num, site_obj.name, vendor.name,
                                                            site_product_obj.product.name, vendor_min, safety_stock,
                                                               site_obj.custom1), 'vendor_mins.txt')


def get_str_element(lst, el):
    a = lst[el]
    if a == "":
        return ""
    else:
        a = str(a)
        a = a.strip()
        return a


def get_int_element(lst, el):
    a = lst[el]
    if a == "":
        return 0
    else:
        a = str(a)
        a = a.strip()
        a = int(a)
        return a


def get_float_element(lst, el):
    a = lst[el]
    if a == "":
        return 0.0
    else:
        a = str(a)
        a = a.strip()
        a = float(a)
        return a

