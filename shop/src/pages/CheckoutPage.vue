<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useShopStore } from '../store/shop'
import { api } from '../api/client'
import { CheckCircle, Loader } from '../components/icons.js'

const store = useShopStore()
const router = useRouter()
const items = computed(() => store.cartItemsDetailed)

const form = ref({
  name: store.customer?.name || 'Demo Shopper',
  email: 'demo@shieldshop.test',
  phone: '+1-202-555-0143',
  address: '12 Cedar Avenue, Springfield',
  method: 'card',
  card: '4242 4242 4242 4242',
  expiry: '12/29',
  cvc: '123',
})

const processing = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  processing.value = true
  try {
    const payload = {
      customer_name: form.value.name,
      customer_email: form.value.email,
      customer_phone: form.value.phone,
      address: form.value.address,
      payment_method: form.value.method,
      items: store.cart.map((i) => ({ product_id: i.product_id, quantity: i.quantity })),
    }
    const res = await api.checkout(payload)
    store.setCustomer({
      customer_id: res.customer_id,
      merchant_id: res.merchant_id,
      name: form.value.name,
      email: form.value.email,
      txn: res.transaction_id,
      total: res.total,
    })
    store.clearCart()
    router.push({ name: 'confirmation', params: { txn: res.transaction_id } })
  } catch (e) {
    error.value = e.message
  } finally {
    processing.value = false
  }
}
</script>

<template>
  <section v-if="!items.length" class="py-20 text-center text-slate-500">
    <p>Your cart is empty.</p>
    <button @click="router.push('/shop')" class="btn-primary mt-4">Shop now</button>
  </section>

  <section v-else class="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
    <form @submit.prevent="submit" class="space-y-5">
      <h1 class="text-xl font-bold">Checkout</h1>

      <fieldset class="card space-y-4 p-5">
        <legend class="px-1 text-sm font-semibold text-slate-700">Contact & shipping</legend>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm"><span class="mb-1 block text-slate-500">Full name</span><input v-model="form.name" class="input" required /></label>
          <label class="text-sm"><span class="mb-1 block text-slate-500">Email</span><input v-model="form.email" type="email" class="input" required /></label>
          <label class="text-sm"><span class="mb-1 block text-slate-500">Phone</span><input v-model="form.phone" class="input" /></label>
          <label class="text-sm"><span class="mb-1 block text-slate-500">Address</span><input v-model="form.address" class="input" /></label>
        </div>
      </fieldset>

      <fieldset class="card space-y-4 p-5">
        <legend class="px-1 text-sm font-semibold text-slate-700">Mock payment</legend>
        <div class="flex gap-2">
          <button type="button" v-for="m in ['card', 'upi', 'wallet']" :key="m" @click="form.method = m"
            :class="['badge px-4 py-2 capitalize', form.method === m ? 'bg-brand-600 text-white' : 'bg-white text-slate-600 ring-1 ring-slate-200']">{{ m }}</button>
        </div>
        <div v-if="form.method === 'card'" class="grid gap-3 sm:grid-cols-3">
          <label class="text-sm sm:col-span-3"><span class="mb-1 block text-slate-500">Card number</span><input v-model="form.card" class="input" placeholder="4242 4242 4242 4242" /></label>
          <label class="text-sm"><span class="mb-1 block text-slate-500">Expiry</span><input v-model="form.expiry" class="input" placeholder="MM/YY" /></label>
          <label class="text-sm"><span class="mb-1 block text-slate-500">CVC</span><input v-model="form.cvc" class="input" placeholder="123" /></label>
        </div>
        <p v-else class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
          {{ form.method === 'upi' ? 'Pay via UPI (demo).' : 'Pay via wallet (demo).' }} No real charge is made.
        </p>
        <div class="flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-2.5 text-xs text-emerald-700">
          <CheckCircle class="h-4 w-4" /> This is a demo payment. The order is auto-marked delivered so you can try returns.
        </div>
      </fieldset>

      <div v-if="error" class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{{ error }}</div>

      <button :disabled="processing" class="btn-dark w-full">
        <Loader v-if="processing" class="h-4 w-4 animate-spin" />
        {{ processing ? 'Processing...' : `Pay $${store.cartTotal.toFixed(2)} & place order` }}
      </button>
    </form>

    <aside class="card h-fit p-5 lg:sticky lg:top-24">
      <h2 class="text-base font-semibold">Order summary</h2>
      <ul class="mt-4 space-y-3">
        <li v-for="i in items" :key="i.product_id" class="flex items-center gap-3">
          <img :src="i.image" class="h-11 w-11 rounded-lg object-cover" />
          <div class="min-w-0 flex-1">
            <div class="truncate text-sm font-medium">{{ i.name }}</div>
            <div class="text-xs text-slate-500">Qty {{ i.quantity }}</div>
          </div>
          <div class="text-sm font-semibold">${{ (i.price * i.quantity).toFixed(2) }}</div>
        </li>
      </ul>
      <dl class="mt-4 space-y-2 border-t border-slate-100 pt-4 text-sm">
        <div class="flex justify-between font-bold"><dt>Total</dt><dd>${{ store.cartTotal.toFixed(2) }}</dd></div>
      </dl>
    </aside>
  </section>
</template>
