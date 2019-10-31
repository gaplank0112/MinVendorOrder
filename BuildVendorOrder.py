'''
This script is scheduled by the Inventory Policy script if an item from a vendor falls below the reorder point
In the first pass, each item has the inventory position at now + lead time (calculated during the inventory review)
reviewed against reorder point (reorderpoint DOS from the UI * daily sales starting at now + lead time (4 weeks of
forecast divided by 28)). If an item is below reorder point, we order the minimum units followed by increments of lot
size until over reorder point. We do this for all products from the same vendor. If the total is greater than the
vendor order min, we stop. If not, we find the lowest DOS of all items from the same vendor, add one day and find all
products below that mark. We add either minimum order if the first time it is ordered or a lot size of each in the
smaller DOS list and then recalculate DOS. This loop continues, slowly increasing the DOS and adding while also
balancing the DOS of all items ordered from the vendor.  When the vendor min is reached, we place the order and then
reset all variables used for calculation until the next order.

Created 2018-07-22 by Greg Plank
'''

import sys
sys.path.append("C:\Python26\SCG_64\Lib")
import sim_server

low, med, high = 2, 5, 8
debug_obj = sim_server.Debug()
model_obj = sim_server.Model()


def main(site_obj, vendor_obj):
    debug_obj.trace(low, "-" * 20)
    debug_obj.trace(low, "BuildVendorOrder_03 called at " + sim_server.NowAsString())

    site_vendor_product_dict = model_obj.getcustomattribute("SiteVendorProductDictionary")
    product_list = site_vendor_product_dict[site_obj.name][vendor_obj.name]
    DOS_dict = build_DOS_dict(site_obj,product_list)
    vendor_order_minimum = get_vendor_minimum(site_obj, product_list[0])  # we can use just one item in the dictionary

    # in the first pass, we just get anyone below reorder point to above reorder point
    fill_below_mins(site_obj, product_list, DOS_dict)

    # check to see if the order quantity total is above the requirement
    total_order_quantity = calculate_order_quantity(site_obj, product_list)
    # debug_obj.trace(low, " Total order quantity after first pass is %s" % total_order_quantity)
    # debug_obj.trace(low, " ")

    # if we still need more, we sort the list by lowest DOS and then add in order until we reach fill.... re-sorrting
    # after each time through the list.

    if total_order_quantity < vendor_order_minimum:
        while total_order_quantity < vendor_order_minimum:
            # sort the list of products from lowest DOS to highest
            sorted_product_list = get_DOS_list(DOS_dict)
            total_order_quantity = add_another_lot(site_obj,sorted_product_list, total_order_quantity, DOS_dict)
            # debug_obj.trace(low, " Total vendor order quantity after this pass is %s" % total_order_quantity)
            # debug_obj.trace(low, " ")

    place_the_order(site_obj,product_list, DOS_dict)
    reset_sp_info(site_obj,product_list)


def build_DOS_dict(site_obj, product_list):
    # debug_obj.trace(low,"  Building DOS dictionary")
    DOS_dict = {}
    for product_name in product_list:
        site_product_obj = site_obj.getsiteproduct(product_name)
        sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
        DOS = calculate_DOS(sp_info)
        # debug_obj.trace(med,"   %s, future inventory %s, daily sales %s, "
        #                    "DOS %s" % (product_name,
        #                                sp_info.future_inventory_position + sp_info.future_order_quantity,
        #                                sp_info.future_daily_sales, DOS))
        DOS_dict[product_name] = DOS

    return DOS_dict


def get_vendor_minimum(site_obj, product_name):
    site_product_obj = site_obj.getsiteproduct(product_name)
    sp_info = site_product_obj.getcustomattribute("SiteProductInfo")

    return sp_info.vendor_order_minimum


def calculate_DOS(sp_info):
    if sp_info.future_daily_sales <= 0.0:
        DOS = 9999.0
    else:
        DOS = (sp_info.future_inventory_position + sp_info.future_order_quantity) / sp_info.future_daily_sales
    return DOS


def get_DOS_list(DOS_dict):
    # Find the product with lowest DOS. Add 1 to DOS. return all items less than lowest DOS + 1
    # debug_obj.trace(low, "  Building DOS list")
    DOS_list = []
    for k,v in DOS_dict.iteritems():
        # debug_obj.trace(high, "   DOS list %s %s" % (k,v))
        DOS_list.append((k,v))
    # debug_obj.trace(med, "   DOS list %s" % DOS_list)
    lowest_DOS = min([x[1] for x in DOS_list])
    target_DOS = lowest_DOS + 1.0
    DOS_list = [x for x in DOS_list if x[1] < target_DOS]
    DOS_list.sort(key=lambda x: x[1])
    sorted_product_list = [x[0] for x in DOS_list]
    # debug_obj.trace(low,"    Add-to product list %s" % sorted_product_list)
    # debug_obj.trace(low, " ")

    return sorted_product_list


def fill_below_mins(site_obj, product_list, DOS_dict):
    # debug_obj.trace(low, '\n' + "  First pass - fill below mins")
    for product_name in product_list:
        site_product_obj = site_obj.getsiteproduct(product_name)
        sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
        inventory_position = sp_info.future_inventory_position
        # debug_obj.trace(med,"   %s %s inventory position = %s, future daily sales = %s" %(site_obj.name, product_name,
        #                                                          inventory_position, sp_info.future_daily_sales))
        if sp_info.future_daily_sales > 0.0 or inventory_position < 0.0:
            order_quantity = 0.0
            minimum_first_order_quantity = sp_info.minimum_order_qty
            order_lot_size = sp_info.order_lot_size
            min_inventory = site_product_obj.reorderptDOS * sp_info.future_daily_sales
            # debug_obj.trace(med,"    IP %s, min inv %s, min first order %s, order lot size %s" %
            #                 (inventory_position, min_inventory, minimum_first_order_quantity, order_lot_size))
            if inventory_position < min_inventory: # add one lot of the product minimum order quantity
                order_quantity = minimum_first_order_quantity
                inventory_position += order_quantity
                sp_info.min_order_used = True
                # debug_obj.trace(med, "      First order quantity %s, new IP %s" % (order_quantity,inventory_position))

            # if inventory position is still below min, add in increments of lot size to get over min
            while inventory_position < min_inventory:
                order_quantity += order_lot_size
                inventory_position += order_lot_size
                # debug_obj.trace(med, "       Another lot ordered -> lot size %s, new order quantity %s, new IP %s" %
                #                 (order_lot_size, order_quantity, inventory_position))

            if order_quantity > 0.0:
                sp_info.future_order_quantity = order_quantity
            new_DOS = calculate_DOS(sp_info)
            # debug_obj.trace(med, "   Total order for product %s, new DOS %s" %
            #                 (sp_info.future_order_quantity, new_DOS))
            # debug_obj.trace(med, "   ----------")
            DOS_dict[product_name] = new_DOS


def calculate_order_quantity(site_obj, product_list):
    total_order_quantity = 0.0
    for product_name in product_list:
        site_product_obj = site_obj.getsiteproduct(product_name)
        sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
        total_order_quantity += sp_info.future_order_quantity

    return total_order_quantity


def add_another_lot(site_obj, product_list, total_order_quantity, DOS_dict):
    # debug_obj.trace(low, "  Add another lot")
    for product_name in product_list:
        site_product_obj = site_obj.getsiteproduct(product_name)
        sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
        if sp_info.min_order_used is False: # if we have not used the minimum order quantity yet, we should now
            order_lot_size = sp_info.minimum_order_qty
            sp_info.min_order_used = True
        else:
            order_lot_size = sp_info.order_lot_size
        order_quantity = sp_info.future_order_quantity
        base_inventory_position = sp_info.future_inventory_position
        new_inventory_position = base_inventory_position + order_quantity + order_lot_size
        if sp_info.future_daily_sales <= 0.0:
            DOS = 9999.0
        else:
            DOS = new_inventory_position / sp_info.future_daily_sales
        # debug_obj.trace(low, "   %s %s, base ip %s, previous order quantity %s, order lot size %s, "
        #                      "new inventory position %s, DOS %s" %
        #                 (site_obj.name, product_name, base_inventory_position, order_quantity,
        #                  order_lot_size, new_inventory_position, DOS))
        order_quantity += order_lot_size
        total_order_quantity += order_lot_size
        sp_info.future_order_quantity = order_quantity
        new_DOS = calculate_DOS(sp_info)
        # debug_obj.trace(med, "   Total order for product %s, new DOS %s" %
        #                 (sp_info.future_order_quantity, new_DOS))
        # debug_obj.trace(med, "   ----------")
        DOS_dict[product_name] = new_DOS

    return total_order_quantity


def place_the_order(site_obj, product_list, DOS_dict):
    # debug_obj.trace(low,"  Creating an order for the vendor")
    for product_name in product_list:
        site_product_obj = site_obj.getsiteproduct(product_name)
        sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
        DOS = calculate_DOS(sp_info)
        # debug_obj.trace(low, "    Order details: %s units of %s for %s DOS = %s" % (sp_info.future_order_quantity,
        #                                                                         product_name, site_obj.name, DOS))
        if sp_info.future_order_quantity > 0.0:
            order_pass = sim_server.CreateOrder(product_name, sp_info.future_order_quantity, site_obj.name)
            if order_pass.detail.quantity == sp_info.future_order_quantity:
                debug_obj.trace(high, "     Order passed")
            else:
                debug_obj.trace(high,"     Order failed")
            DOS_str = "%.1f" % DOS_dict[product_name]
            order_pass.ordernumber = DOS_str

            
def reset_sp_info(site_obj, product_list):
    # debug_obj.trace(low,"  Reset SP info")
    for product_name in product_list:
        site_product_obj = site_obj.getsiteproduct(product_name)
        sp_info = site_product_obj.getcustomattribute("SiteProductInfo")
        sp_info.future_inventory_position = 0.0
        sp_info.future_daily_sales = 0.0
        sp_info.future_order_quantity = 0.0
        sp_info.min_order_used = False




