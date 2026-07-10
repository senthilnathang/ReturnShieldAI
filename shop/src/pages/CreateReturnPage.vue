<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { ArrowLeft, Upload, Image as ImageIcon, Shield, Loader, CheckCircle, AlertTriangle } from '../components/icons.js'

const props = defineProps({ orderId: { type: String, required: true } })
const router = useRouter()

const loading = ref(true)
const submitting = ref(false)
const error = ref('')

const returnableItems = ref([])
const eligibility = ref(null)

const form = ref({
  reason_category: 'DAMAGED_PRODUCT',
  return_reason: 'Item arrived damaged',
  detailed_description: '',
  condition: 'damaged',
  method: 'PICKUP',
  pickup_address: '12 Cedar Avenue, Springfield',
  refund_method: 'ORIGINAL',
  quantities: {},
})

const imageDataUrl = ref('')
const imageName = ref('')
const imageMime = ref('')
const imagePreview = ref('')
const ocrResult = ref(null)

const REASONS = [
  ['DAMAGED_PRODUCT', 'Damaged product'],
  ['DEFECTIVE_PRODUCT', 'Defective product'],
  ['WRONG_PRODUCT', 'Wrong product received'],
  ['EMPTY_BOX', 'Empty box received'],
  ['MISSING_ACCESSORIES', 'Missing accessories'],
  ['NOT_AS_DESCRICTED', 'Not as described'],
  ['CHANGED_MIND', 'Changed my mind'],
  ['SIZE_FIT', 'Size / fit issue'],
]
const CONDITIONS = ['unused', 'damaged', 'empty_box', 'used', 'defective']
const METHODS = [['PICKUP', 'Doorstep pickup'], ['DROP_OFF', 'Drop-off point'], ['SELF_SHIP', 'Self-ship']]
const REFUNDS = [['ORIGINAL', 'Original payment'], ['STORE_CREDIT', 'Store credit'], ['WALLET', 'Wallet']]

const needsDescription = computed(() =>
  ['DAMAGED_PRODUCT', 'DEFECTIVE_PRODUCT', 'WRONG_PRODUCT', 'EMPTY_BOX', 'MISSING_ACCESSORIES'].includes(form.value.reason_category)
)
const totalQty = computed(() => Object.values(form.value.quantities).reduce((a, b) => a + Number(b || 0), 0))

onMounted(async () => {
  try {
    const [items, elig] = await Promise.all([
      api.getReturnableItems(props.orderId),
      api.getEligibility(props.orderId),
    ])
    returnableItems.value = items
    eligibility.value = elig
    items.forEach((i) => (form.value.quantities[i.order_item_id] = i.available_return_quantity))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function onFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    imageDataUrl.value = reader.result
    imageName.value = file.name
    imageMime.value = file.type
    imagePreview.value = reader.result
    ocrResult.value = null
  }
  reader.readAsDataURL(file)
}

async function runOcr() {
  if (!imageDataUrl.value) return
  ocrResult.value = { loading: true }
  try {
    const res = await api.compareImage(props.orderId, imageDataUrl.value, imageName.value, imageMime.value)
    ocrResult.value = res
  } catch (e) {
    ocrResult.value = { error: e.message }
  }
}

async function submit() {
  error.value = ''
  if (needsDescription.value && !form.value.detailed_description.trim()) {
    error.value = 'A detailed description is required for this return reason.'
    return
  }
  if (form.value.method === 'PICKUP' && !form.value.pickup_address.trim()) {
    error.value = 'Pickup address is required for doorstep pickup.'
    return
  }
  if (totalQty.value <= 0) {
    error.value = 'Select at least one item to return.'
    return
  }

  submitting.value = true
  try {
    const items = returnableItems.value
      .filter((i) => Number(form.value.quantities[i.order_item_id] || 0) > 0)
      .map((i) => ({
        order_item_id: i.order_item_id,
        quantity: Number(form.value.quantities[i.order_item_id]),
        serial_number: i.requires_serial ? form.value.serial || null : null,
      }))

    const payload = {
      return_reason_category: form.value.reason_category,
      return_reason: form.value.return_reason,
      detailed_description: form.value.detailed_description,
      condition_reported: form.value.condition,
      return_method: form.value.method,
      pickup_address_id: form.value.method === 'PICKUP' ? form.value.pickup_address : null,
      preferred_refund_method: form.value.refund_method,
      items,
      attachments: imageDataUrl.value
        ? [{ id: imageName.value, file_type: imageMime.value, file_url: imageDataUrl.value, image_type: 'return_image', uploaded_by: 'customer' }]
        : [],
    }
    const result = await api.createReturn(props.orderId, payload, { 'X-User-Id': 'shop-customer' })
    router.push(`/returns/${result.id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <button @click="router.push(`/orders/${props.orderId}`)" class="btn-ghost mb-4 text-xs">
    <ArrowLeft class="h-4 w-4" /> Back to order
  </button>

  <div v-if="loading" class="grid place-items-center py-20 text-slate-400">
    <Loader class="h-6 w-6 animate-spin" />
  </div>

  <div v-else-if="!eligibility?.eligible && !eligibility?.can_override" class="card border-amber-200 bg-amber-50 p-5 text-sm text-amber-700">
    <AlertTriangle class="mb-1 h-4 w-4" /> {{ eligibility?.message || 'This order is not eligible for return.' }}
  </div>

  <form v-else @submit.prevent="submit" class="space-y-5">
    <div class="card p-5">
      <h1 class="text-lg font-bold">Start a return</h1>
      <p class="text-sm text-slate-500">Powered by ReturnShield AI — your request is screened for fraud risk and image verification.</p>
    </div>

    <fieldset class="card space-y-4 p-5">
      <legend class="px-1 text-sm font-semibold text-slate-700">Items to return</legend>
      <div v-for="i in returnableItems" :key="i.order_item_id" class="flex items-center justify-between gap-4">
        <div>
          <div class="font-medium">{{ i.product_name }}</div>
          <div class="text-xs text-slate-500">SKU {{ i.sku }} · Available {{ i.available_return_quantity }}</div>
        </div>
        <label class="flex items-center gap-2 text-sm">
          Qty
          <input type="number" min="0" :max="i.available_return_quantity" v-model.number="form.quantities[i.order_item_id]"
            class="input w-20 text-center" />
        </label>
      </div>
    </fieldset>

    <fieldset class="card space-y-4 p-5">
      <legend class="px-1 text-sm font-semibold text-slate-700">Reason & condition</legend>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="text-sm"><span class="mb-1 block text-slate-500">Reason category</span>
          <select v-model="form.reason_category" class="input">
            <option v-for="[v, l] in REASONS" :key="v" :value="v">{{ l }}</option>
          </select>
        </label>
        <label class="text-sm"><span class="mb-1 block text-slate-500">Condition</span>
          <select v-model="form.condition" class="input">
            <option v-for="c in CONDITIONS" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
      </div>
      <label class="text-sm"><span class="mb-1 block text-slate-500">Return reason</span>
        <input v-model="form.return_reason" class="input" />
      </label>
      <label class="text-sm">
        <span class="mb-1 block flex items-center gap-2 text-slate-500">
          Detailed description
          <span v-if="needsDescription" class="badge bg-rose-50 text-rose-600">required</span>
        </span>
        <textarea v-model="form.detailed_description" rows="3" class="input" placeholder="Describe the issue..."></textarea>
      </label>
    </fieldset>

    <fieldset class="card space-y-4 p-5">
      <legend class="px-1 text-sm font-semibold text-slate-700">Logistics & refund</legend>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="text-sm"><span class="mb-1 block text-slate-500">Return method</span>
          <select v-model="form.method" class="input">
            <option v-for="[v, l] in METHODS" :key="v" :value="v">{{ l }}</option>
          </select>
        </label>
        <label class="text-sm"><span class="mb-1 block text-slate-500">Preferred refund</span>
          <select v-model="form.refund_method" class="input">
            <option v-for="[v, l] in REFUNDS" :key="v" :value="v">{{ l }}</option>
          </select>
        </label>
      </div>
      <label v-if="form.method === 'PICKUP'" class="text-sm"><span class="mb-1 block text-slate-500">Pickup address</span>
        <input v-model="form.pickup_address" class="input" />
      </label>
    </fieldset>

    <fieldset class="card space-y-4 p-5">
      <legend class="px-1 flex items-center gap-2 text-sm font-semibold text-slate-700">
        <Upload class="h-4 w-4" /> Upload a picture (optional)
      </legend>
      <p class="text-xs text-slate-500">A photo of the item/label is run through AI image verification (OCR + mismatch detection).</p>

      <label class="flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-center hover:border-brand-400">
        <ImageIcon class="h-8 w-8 text-slate-400" />
        <span class="mt-2 text-sm font-medium text-slate-600">{{ imageName || 'Click to upload an image' }}</span>
        <span class="text-xs text-slate-400">PNG / JPG</span>
        <input type="file" accept="image/*" class="hidden" @change="onFile" />
      </label>

      <div v-if="imagePreview" class="flex flex-wrap items-start gap-4">
        <img :src="imagePreview" class="h-28 w-28 rounded-xl object-cover ring-1 ring-slate-200" />
        <div class="flex-1">
          <button type="button" @click="runOcr" class="btn-ghost text-xs">
            <Shield class="h-4 w-4" /> Run image verification
          </button>
          <div v-if="ocrResult?.loading" class="mt-2 flex items-center gap-2 text-xs text-slate-500">
            <Loader class="h-3.5 w-3.5 animate-spin" /> Analyzing image...
          </div>
          <div v-else-if="ocrResult && !ocrResult.error" class="mt-2 rounded-xl border border-slate-200 bg-white p-3 text-xs">
            <div class="flex items-center gap-2 font-medium" :class="ocrResult.matched ? 'text-emerald-600' : 'text-amber-600'">
              <CheckCircle v-if="ocrResult.matched" class="h-4 w-4" />
              <AlertTriangle v-else class="h-4 w-4" />
              {{ ocrResult.matched ? 'Image matches the order' : 'Possible mismatch detected' }} · confidence {{ Number(ocrResult.confidence || 0).toFixed(0) }}%
            </div>
            <p v-if="ocrResult.summary" class="mt-1 text-slate-500">{{ ocrResult.summary }}</p>
          </div>
          <div v-else-if="ocrResult?.error" class="mt-2 text-xs text-slate-400">{{ ocrResult.error }} (your picture will still be attached.)</div>
        </div>
      </div>
    </fieldset>

    <div v-if="error" class="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      <AlertTriangle class="mb-1 h-4 w-4" /> {{ error }}
    </div>

    <button :disabled="submitting" class="btn-dark w-full">
      <Loader v-if="submitting" class="h-4 w-4 animate-spin" />
      {{ submitting ? 'Submitting...' : 'Submit return request' }}
    </button>
    <p class="text-center text-[11px] text-slate-400">Submitting triggers ReturnShield AI fraud screening and image review.</p>
  </form>
</template>
