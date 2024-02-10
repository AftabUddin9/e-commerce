from django.shortcuts import render, HttpResponseRedirect, redirect
from django.urls import reverse
from django.contrib import messages

# models and forms
from App_Order.models import Order, Cart
from App_Payment.models import BillingAddress
from App_Payment.forms import BillingForm

from django.contrib.auth.decorators import login_required

# for payment
import requests
from sslcommerz_lib import SSLCOMMERZ
from decimal import Decimal
import socket

from django.views.decorators.csrf import csrf_exempt

# Create your views here.

@login_required
def checkout(request):
    saved_address = BillingAddress.objects.get_or_create(user=request.user)
    saved_address=saved_address[0]
    form = BillingForm(instance=saved_address)
    if request.method == 'POST':
        form = BillingForm(request.POST, instance=saved_address)
        if form.is_valid():
            form.save()
            form = BillingForm(instance=saved_address)
            messages.success(request, f"Shipping Address Saved!")
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    order_items = order_qs[0].orderitems.all()
    order_total = order_qs[0].get_totals()
    return render(request, 'App_Payment/checkout.html', context={'form': form, 'order_items': order_items, 'order_total': order_total, 'saved_address': saved_address})


@login_required
def payment(request):
    saved_address = BillingAddress.objects.get_or_create(user=request.user)[0]
    if not saved_address.is_fully_filled():
        messages.info(request, f'Please Complete Shipping Address')
        return redirect('App_Payment:checkout')
    if not request.user.profile.is_fully_filled():
        messages.info(request, f'Please Complete Profile Details')
        return redirect('App_Login:profile')
    
    current_user = request.user
    store_id = 'abc65c4a46c2db1b'
    API_key = 'abc65c4a46c2db1b@ssl'
    settings = { 'store_id': store_id, 'store_pass': API_key, 'issandbox': True }
    status_url = request.build_absolute_uri(reverse('App_Payment:complete'))
    order_qs = Order.objects.filter(user=request.user, ordered=False)[0]
    order_items = order_qs.orderitems.all()
    order_items_count = order_qs.orderitems.count()
    order_total = order_qs.get_totals()

    sslcommez = SSLCOMMERZ(settings)
    post_body = {}
    post_body['total_amount'] = Decimal(order_total)
    post_body['currency'] = "BDT"
    post_body['tran_id'] = "12345"
    post_body['success_url'] = status_url
    post_body['fail_url'] = status_url
    post_body['cancel_url'] = status_url
    post_body['emi_option'] = 0
    post_body['cus_name'] = current_user.profile.full_name
    post_body['cus_email'] = current_user.email
    post_body['cus_phone'] = current_user.profile.phone
    post_body['cus_add1'] = current_user.profile.address_1
    post_body['cus_city'] = current_user.profile.city
    post_body['cus_country'] = current_user.profile.country
    post_body['shipping_method'] = "Courier"
    post_body['multi_card_name'] = ""
    post_body['num_of_item'] = order_items_count
    post_body['product_name'] = order_items
    post_body['product_category'] = "Mixed"
    post_body['product_profile'] = "None"

    post_body['ship_name'] = current_user.profile.full_name
    post_body['ship_add1'] = saved_address.address
    post_body['ship_city'] = saved_address.city
    post_body['ship_postcode'] = saved_address.zipcode
    post_body['ship_country'] = saved_address.country
    
    response_data = sslcommez.createSession(post_body)
    return redirect(response_data["GatewayPageURL"])


@csrf_exempt
def complete(request):
    if request.method == "POST" or request.method == "post":
        payment_data = request.POST
        status = payment_data['status']

        if status == 'VALID':
            val_id = payment_data['val_id']
            tran_id = payment_data['tran_id']
            messages.success(request, f"Your Payment Completed Successfully! Page will be redirected!")
            return HttpResponseRedirect(reverse('App_Payment:purchase', kwargs={'val_id': val_id, 'tran_id': tran_id}))
        elif status == 'FAILED':
            messages.warning(request, f"Your Payment Failed! Please Try Again! Page will be redirected!")
    return render(request, "App_Payment/complete.html", context={})


@login_required
def purchase(request, val_id, tran_id):
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    order = order_qs[0]
    orderId = tran_id
    order.ordered = True
    order.orderId = orderId
    order.paymentId = val_id
    order.save()
    cart_items = Cart.objects.filter(user=request.user, purchased=False)
    for item in cart_items:
        item.purchased = True
        item.save()
    return HttpResponseRedirect(reverse('App_Shop:home'))


@login_required
def order_view(request):
    try:
        orders = Order.objects.filter(user=request.user, ordered=True)
        context = {'orders': orders}
    except:
        messages.warning(request, "You do not have an active order")
        return redirect("App_Shop:home")
    return render(request, 'App_Payment/order.html', context)