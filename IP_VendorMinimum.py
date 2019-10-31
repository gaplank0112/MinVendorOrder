'''
This script ia an Inventory policy
When triggered we get a single site product. We find the vendor associated with that product.
With the site and vendor,we go to the dictionary and find all products supplied by the vendor to the site.
We calculate and review the inventory position against reorder point.
When one product is below reorder point,all product from the same vendor is evaluated to build an order.
'''

import sys
import sim_server
import datetime
import BuildVendorOrder
sys.path.append("C:\Python26\SCG_64\Lib")


low,med,high = 2,5,8
debug_obj = sim_server.Debug()
model_obj = sim_server.Model()


def main(site_obj,product_obj,order_qty):
    debug_obj.trace(low,"-" * 20)
    debug_obj.trace(low,"IP_VendorMinimum called at " + sim_server.NowAsString())

    # check to see if this product has been recently reviewed - no need to do it again.
    trigger_sp_obj = site_obj.getsiteproduct(product_obj.name)
    trigger_sp_info = get_sp_info (trigger_sp_obj)
    if trigger_sp_info == 0:
        return
    if trigger_sp_info.inventory_reviewed == datetime.datetime.utcfromtimestamp(sim_server.Now()):
        return

    # We find the vendor associated with this site - product
    vendor_obj = trigger_sp_obj.sources[0]

    # determine the current week index and the week index at current time + lead time of the trigger site product
    trigger_sp_lead_time = trigger_sp_info.lead_time
    current_dt = datetime.datetime.utcfromtimestamp(sim_server.Now()).date()
    week_idx = abs(int(get_week_idx(current_dt)))
    current_plus_lead_time = current_dt + datetime.timedelta(days=trigger_sp_lead_time)
    week_lead_time_idx = get_week_idx(current_plus_lead_time)

    # Review all products for items below reorder point. Collect the list of unique vendor names to review for
    # vendor minimum order size

    # debug_obj.trace(low," Checking inventory positions for site %s vendor %s" % (site_obj.name,vendor_obj.name))

    # Get the list of products to loop through
    site_vendor_product_dict = model_obj.getcustomattribute("SiteVendorProductDictionary")
    site_vendor_product_list = site_vendor_product_dict[site_obj.name][vendor_obj.name]

    create_order = False
    for product_name in site_vendor_product_list:
        site_product_obj = site_obj.getsiteproduct(product_name)
        sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
        lead_time = sp_info.lead_time
        lead_time_demand = calculate_future_demand(site_product_obj,lead_time,week_idx)
        future_inventory_position = calculate_inventory_position(site_product_obj,lead_time_demand)
        future_week_idx = week_lead_time_idx
        if sp_info.lead_time != trigger_sp_lead_time:
            current_plus_lead_time = current_dt + datetime.timedelta(days=sp_info.lead_time)
            future_week_idx = abs(int(get_week_idx(current_plus_lead_time)))
        future_daily_sales = calculate_future_daily_sales(site_product_obj,sp_info,future_week_idx)
        reorder_point = calculate_reorder_point(site_product_obj,future_daily_sales)
        sp_info.inventory_reviewed = datetime.datetime.utcfromtimestamp(sim_server.Now())
        msg = " IP %s,reorder point %s for %s %s" % (future_inventory_position,reorder_point,site_obj.name,
                                                      product_name)
        if future_inventory_position < reorder_point:
            create_order = True
            msg += ". IP < reorderpoint triggers an order from %s" % vendor_obj.name

        # debug_obj.trace(low,msg)

        # add this info to sp_info
        sp_info.future_inventory_position = future_inventory_position
        sp_info.future_daily_sales = future_daily_sales
        sp_info.inventory_reviewed = datetime.datetime.utcfromtimestamp(sim_server.Now())
        sp_info.lead_time_demand = lead_time_demand

        report_inventory_position(site_product_obj,sp_info)

    if create_order is True:
        # debug_obj.trace(low,"  Building an order for vendor %s" % vendor_obj.name)
        # BuildVendorOrder_01.main(site_obj,vendor_obj)
        BuildVendorOrder.main(site_obj,vendor_obj)


def get_sp_info(sp_obj):
    try:
        sp_info = sp_obj.getcustomattribute("SiteProductInfo")
        return sp_info
    except:
        debug_obj.logerror("Unable to find site product info for %s %s" % (sp_obj.site.name,sp_obj.product.name))
    return 0


def calculate_future_daily_sales(sp_obj,sp_info,future_week_idx):
    future_forecast = 0.0
    future_forecast_values = []
    for i in list(range(future_week_idx,future_week_idx + 4)):
        forecast_length = sp_obj.DOSforecastcount
        if forecast_length <= 0:
            debug_obj.logerror("No forecast for %s %s" % (sp_obj.site.name, sp_obj.product.name))
            return 0.0  # There is no forecast, so no future daily sales

        if i > forecast_length - 1:
            div,mod = divmod(i,forecast_length)
            # debug_obj.trace(high,"   Loop to begining of forecast idx,length,div,mod,new idx %s,%s,%s,%s %s" %
            #                (i,forecast_length,div,mod,i - (div * forecast_length)))
            i = i - (div * forecast_length)
        future_forecast += sp_obj.getdosforecast(i)
        future_forecast_values.append(sp_obj.getdosforecast(i))
    future_daily_sales = future_forecast / 28  # we take 4 weeks of forecast and divide by 28 days to get a daily rate
    # debug_obj.trace(low,"    Calculate future daily sales week idx = %s,values = %s,"
    #                      "rate = %s" % (future_week_idx,future_forecast_values,future_daily_sales))
    sp_info.future_forecast = future_forecast

    return future_daily_sales


def calculate_inventory_position(sp_obj,lead_time_demand):
    product_name = sp_obj.product.name
    sp_info = sp_obj.getcustomattribute("SiteProductInfo")
    # debug_obj.trace(low,'\n' + "  Execute calculate_inventory_position for %s %s" %
    #                 (sp_obj.site.name,product_name))
    lead_time = sp_info.lead_time
    due_in_quantity = sp_obj.currentorderquantity
    due_out_quantity = sp_obj.backorderquantity
    on_hand_inventory = sp_obj.inventory
    # debug_obj.trace(low,"   Lead time %s| due-in %s| due-out %s| on-hand %s| future demand %s" %
    #                (lead_time,due_in_quantity,due_out_quantity,
    #                on_hand_inventory,lead_time_demand))
    inventory_position = on_hand_inventory + due_in_quantity - due_out_quantity - lead_time_demand
    debug_obj.trace(low,"   Inventory position = %s" % inventory_position)

    return inventory_position


def calculate_reorder_point(sp_obj,daily_sales):
    # debug_obj.trace(low,'\n' + "  Execute calculate_reorder_point ")
    reorder_pt_days = sp_obj.reorderptDOS
    # debug_obj.trace(low,"   reorder point days %s " % reorder_pt_days)
    # debug_obj.trace(low,"   daily sales %s" % daily_sales)
    reorder_point = reorder_pt_days * daily_sales
    # debug_obj.trace(low,"   reorder point %s" % reorder_point)

    return reorder_point


def get_customer_product_obj(cz_obj,product_name):
    for product_obj in cz_obj.products:
        debug_obj.trace(low,"Find a match for %s. Checking %s" % (product_name,product_obj.product.name))
        if product_obj.product.name == product_name:
            debug_obj.trace(low,"   Found a match")
            customer_product_obj = product_obj
            return customer_product_obj


def get_week_idx(current_dt):
    start_dt = model_obj.starttime.date()
    current_dt_wk = int(current_dt.strftime("%U"))
    if current_dt_wk == 53:
        current_dt_wk = 0
    start_dt_wk = int(start_dt.strftime("%U"))
    if start_dt_wk == 53:
        start_dt_wk = 0
    week_idx = current_dt_wk - start_dt_wk
    if week_idx < 0:
        week_idx += 53
    # debug_obj.trace(low," Get week index-> start date %s,current date %s,start date week %s,current date week "
    #                     "%s,week_index %s" % (start_dt,current_dt,start_dt_wk,current_dt_wk,week_idx))
    return week_idx


def calculate_future_demand(sp_obj,lead_time,week_idx):
    # debug_obj.trace(low," -" * 20)
    # debug_obj.trace(low,"  Execute calculate_future_demand for site %s product %s" %
    # (sp_obj.site.name,sp_obj.product.name))
    future_demand_values = []
    starting_date = datetime.datetime.utcfromtimestamp(sim_server.Now())
    future_demand = 0.0
    if lead_time == 0.0: lead_time = 1.0
    week_idx = check_week_idx(sp_obj, week_idx)
    if week_idx == -1:
        return 0  # there is no forecast so no future demand
    while lead_time > 0:
        # debug_obj.trace(high,"  Loop start")
        # debug_obj.trace(high,"   lead time %s, week index %s" % (lead_time, week_idx))
        week_volume = sp_obj.getdosforecast(week_idx)
        # debug_obj.trace(high,"   week volume %s " % week_volume)
        day_of_week = int(starting_date.strftime("%w"))
        # debug_obj.trace(high,"   isoweekday " + str(day_of_week))
        days_in_week = 7 - day_of_week
        # debug_obj.trace(high,"   days in week %s" % days_in_week)
        if week_volume != 0.0:
            daily_sales = week_volume / 7.0
            # debug_obj.trace(high,"   daily sales %s" % daily_sales)
            if lead_time < 7:
                days_in_week = lead_time
            future_demand += daily_sales * days_in_week
            # debug_obj.trace(high,"   future demand %s" % future_demand)
            future_demand_values.append(daily_sales * days_in_week)
        if week_volume == 0.0:
            future_demand_values.append(0.0)
        lead_time -= days_in_week
        starting_date = starting_date + datetime.timedelta(days=days_in_week)
        # debug_obj.trace(high,"   next loop start date %s" % starting_date)
        week_idx += 1
        week_idx = check_week_idx(sp_obj, week_idx)
        # debug_obj.trace(high,"  Loop bottom. Lead time remaining = %s" % lead_time)

    # debug_obj.trace(low,"   Future demand -> %s = %s" % (future_demand_values,int(future_demand)))

    return int(future_demand)


def check_week_idx(sp_obj, week_idx):
    forecast_length = sp_obj.DOSforecastcount
    if week_idx > forecast_length - 1:
        forecast_length = sp_obj.DOSforecastcount
        if forecast_length <= 0:
            debug_obj.logerror("No forecast for %s %s" % (sp_obj.site.name, sp_obj.product.name))
            return -1

        div, mod = divmod(week_idx, forecast_length)
        # debug_obj.trace(high, "    Loop to beginning of forecast idx,length,div,mod,new idx %s,%s,%s,%s %s"
        #                 % (week_idx, forecast_length, div, mod, week_idx - (div * forecast_length)))
        week_idx = week_idx - (div * forecast_length)
    return week_idx


def report_inventory_position(sp_obj,sp_info):
    current_date = datetime.datetime.utcfromtimestamp(sim_server.Now())
    lead_time = sp_info.lead_time
    on_hand_inventory = sp_obj.inventory
    due_in_quantity = sp_obj.currentorderquantity
    due_out_quantity = sp_obj.backorderquantity
    lead_time_demand = sp_info.lead_time_demand
    if lead_time <= 0 or lead_time <= 0.0:
        daily_sales = 0.0
    else:
        daily_sales = lead_time_demand / lead_time
    if daily_sales <= 0.0:
        current_DOS = 9999.0
    else:
        current_DOS = on_hand_inventory / daily_sales
    future_inventory_position = sp_info.future_inventory_position
    future_forecast = sp_info.future_forecast
    future_daily_sales = sp_info.future_daily_sales
    if future_daily_sales <= 0.0:
        future_DOS = 9999.0
    else:
        future_DOS = future_inventory_position / future_daily_sales

    debug_obj.trace(0,'%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s' %
                    (model_obj.scenarioid, model_obj.currentreplication, current_date, sp_obj.site.name,
                     sp_obj.product.name, on_hand_inventory, due_in_quantity, due_out_quantity, lead_time,
                     lead_time_demand, daily_sales,current_DOS, future_inventory_position, future_forecast,
                     future_daily_sales, future_DOS), 'inventory_position.txt')
