<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Trash2 } from '@lucide/vue'
import { useTool } from '../../bridge/useTool'
import type { Rate, Rates, Units, UnitCategory } from './types'

const PREFIX = 'tools.converters.'

const { t, locale } = useI18n()
const tool = useTool('converters')

type Tab = 'units' | 'currencies'
const tab = ref<Tab>('units')

const numberFormat = computed(
  () => new Intl.NumberFormat(locale.value, { maximumSignificantDigits: 10 }),
)
const format = (n: number): string => numberFormat.value.format(n)

// ---- Units ----------------------------------------------------------------

const categories = ref<UnitCategory[]>([])
const category = ref('length')
const source = ref('')
const target = ref('')
const amount = ref<number | null>(1)
const unitResult = ref<number | null>(null)

const currentUnits = computed(
  () => categories.value.find((c) => c.id === category.value)?.units ?? [],
)

// Units of the new category; the conversion itself runs from the watcher on `source`.
function resetUnits(): void {
  const units = currentUnits.value
  source.value = units[0] ?? ''
  target.value = units[1] ?? units[0] ?? ''
}

let unitSeq = 0
async function convertUnit(): Promise<void> {
  const value = amount.value
  const units = currentUnits.value
  // Ignore a selection that belongs to the previous category, while the watcher catches up.
  if (value === null || !units.includes(source.value) || !units.includes(target.value)) return
  const seq = ++unitSeq
  try {
    const result = await tool.call<number>('convert_unit', {
      category: category.value,
      value,
      source: source.value,
      target: target.value,
    })
    if (seq === unitSeq) unitResult.value = result
  } catch {
    // useTool has already shown the error toast.
    if (seq === unitSeq) unitResult.value = null
  }
}

watch(category, resetUnits)
watch([amount, source, target], convertUnit)

// ---- Currencies -----------------------------------------------------------

const base = ref('EUR')
const rates = ref<Rate[]>([])
const newCode = ref('')
const newRate = ref<number | null>(null)
const newDate = ref(new Date().toISOString().slice(0, 10))
const from = ref('EUR')
const to = ref('USD')
const money = ref<number | null>(100)
const moneyResult = ref<number | null>(null)

const currencies = computed(() => [base.value, ...rates.value.map((r) => r.code)])

function applyRates(data: Rates): void {
  base.value = data.base
  rates.value = data.rates
  if (!currencies.value.includes(from.value)) from.value = base.value
  if (!currencies.value.includes(to.value)) to.value = currencies.value[1] ?? base.value
}

let moneySeq = 0
async function convertCurrency(): Promise<void> {
  const value = money.value
  if (value === null || !currencies.value.includes(from.value)) return
  if (!currencies.value.includes(to.value)) return
  const seq = ++moneySeq
  try {
    const result = await tool.call<number>('convert_currency', {
      value,
      source: from.value,
      target: to.value,
    })
    if (seq === moneySeq) moneyResult.value = result
  } catch {
    if (seq === moneySeq) moneyResult.value = null
  }
}

watch([money, from, to], convertCurrency)

async function addRate(): Promise<void> {
  if (!newCode.value || newRate.value === null) return
  try {
    const data = await tool.call<Rates>('set_rate', {
      code: newCode.value.trim().toUpperCase(),
      rate: newRate.value,
      day: newDate.value,
    })
    applyRates(data)
    newCode.value = ''
    newRate.value = null
  } catch {
    // useTool has already shown the error toast.
  }
}

async function removeRate(code: string): Promise<void> {
  try {
    applyRates(await tool.call<Rates>('remove_rate', { code }))
  } catch {
    // useTool has already shown the error toast.
  }
}

// ---- Loading --------------------------------------------------------------

async function load(): Promise<void> {
  try {
    const units = await tool.call<Units>('get_units')
    categories.value = units.categories
    resetUnits()
  } catch {
    // useTool has already shown the error toast.
  }
  try {
    applyRates(await tool.call<Rates>('get_rates'))
  } catch {
    // useTool has already shown the error toast.
  }
  // The watcher does not fire on the first values: convert once for the initial selection.
  void convertCurrency()
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="converters">
    <div class="tabs" role="group" :aria-label="t(`${PREFIX}tabsLabel`)">
      <button
        type="button"
        :aria-pressed="tab === 'units'"
        :class="{ on: tab === 'units' }"
        @click="tab = 'units'"
      >
        {{ t(`${PREFIX}tabs.units`) }}
      </button>
      <button
        type="button"
        :aria-pressed="tab === 'currencies'"
        :class="{ on: tab === 'currencies' }"
        @click="tab = 'currencies'"
      >
        {{ t(`${PREFIX}tabs.currencies`) }}
      </button>
    </div>

    <section v-if="tab === 'units'" class="panel">
      <div class="line">
        <label class="field">
          <span>{{ t(`${PREFIX}category`) }}</span>
          <select v-model="category">
            <option v-for="c in categories" :key="c.id" :value="c.id">
              {{ t(`${PREFIX}categories.${c.id}`) }}
            </option>
          </select>
        </label>
      </div>
      <div class="line">
        <label class="field">
          <span>{{ t(`${PREFIX}value`) }}</span>
          <input v-model.number="amount" type="number" step="any" />
        </label>
        <label class="field">
          <span>{{ t(`${PREFIX}from`) }}</span>
          <select v-model="source">
            <option v-for="u in currentUnits" :key="u" :value="u">{{ u }}</option>
          </select>
        </label>
        <label class="field">
          <span>{{ t(`${PREFIX}to`) }}</span>
          <select v-model="target">
            <option v-for="u in currentUnits" :key="u" :value="u">{{ u }}</option>
          </select>
        </label>
      </div>
      <p class="result" data-testid="unit-result">
        <template v-if="unitResult !== null">{{ format(unitResult) }} {{ target }}</template>
      </p>
    </section>

    <section v-else class="panel">
      <h2>{{ t(`${PREFIX}ratesTitle`) }}</h2>
      <p class="hint">{{ t(`${PREFIX}ratesHint`, { base }) }}</p>
      <ul v-if="rates.length > 0" class="rates">
        <li v-for="r in rates" :key="r.code" :data-rate="r.code" class="rate">
          <span class="code">{{ r.code }}</span>
          <span class="value">1 {{ base }} = {{ format(r.rate) }} {{ r.code }}</span>
          <span class="date">{{ r.date }}</span>
          <button
            type="button"
            class="icon"
            :aria-label="t(`${PREFIX}removeRate`, { code: r.code })"
            :title="t(`${PREFIX}removeRate`, { code: r.code })"
            @click="removeRate(r.code)"
          >
            <Trash2 :size="16" aria-hidden="true" />
          </button>
        </li>
      </ul>
      <p v-else class="hint">{{ t(`${PREFIX}noRates`) }}</p>

      <form class="line add" @submit.prevent="addRate">
        <label class="field">
          <span>{{ t(`${PREFIX}code`) }}</span>
          <input v-model="newCode" maxlength="3" placeholder="USD" autocapitalize="characters" />
        </label>
        <label class="field">
          <span>{{ t(`${PREFIX}rateOf`, { base }) }}</span>
          <input v-model.number="newRate" type="number" step="any" min="0" />
        </label>
        <label class="field">
          <span>{{ t(`${PREFIX}date`) }}</span>
          <input v-model="newDate" type="date" />
        </label>
        <button type="submit" class="submit">{{ t(`${PREFIX}addRate`) }}</button>
      </form>

      <h2>{{ t(`${PREFIX}convertTitle`) }}</h2>
      <div class="line">
        <label class="field">
          <span>{{ t(`${PREFIX}amount`) }}</span>
          <input v-model.number="money" type="number" step="any" />
        </label>
        <label class="field">
          <span>{{ t(`${PREFIX}from`) }}</span>
          <select v-model="from">
            <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label class="field">
          <span>{{ t(`${PREFIX}to`) }}</span>
          <select v-model="to">
            <option v-for="c in currencies" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
      </div>
      <p class="result" data-testid="money-result">
        <template v-if="moneyResult !== null">{{ format(moneyResult) }} {{ to }}</template>
      </p>
    </section>
  </div>
</template>

<style scoped>
.converters {
  max-width: 720px;
}
.tabs {
  display: inline-flex;
  margin-bottom: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.tabs button {
  padding: 7px 16px;
  border: none;
  background: var(--bg-elevated);
  color: var(--text-muted);
  font: inherit;
  cursor: pointer;
}
.tabs button.on {
  background: var(--active);
  color: var(--text);
}
.tabs button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.panel {
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-elevated);
}
.panel h2 {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.panel h2:first-child {
  margin-top: 0;
}
.hint {
  color: var(--text-muted);
  margin: 0 0 12px;
}
.line {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 120px;
  flex: 1;
  font-size: 13px;
  color: var(--text-muted);
}
input,
select {
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font: inherit;
}
input:focus-visible,
select:focus-visible,
button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.result {
  margin: 4px 0 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--text);
  min-height: 1.4em;
}
.rates {
  margin: 0 0 16px;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.rate {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 7px 10px;
}
.rate + .rate {
  border-top: 1px solid var(--border);
}
.code {
  font-weight: 600;
  min-width: 48px;
}
.value {
  flex: 1;
}
.date {
  color: var(--text-muted);
  font-size: 13px;
}
.icon {
  display: inline-flex;
  padding: 5px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}
.icon:hover {
  background: var(--active);
}
.add {
  align-items: flex-end;
}
.submit {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--active);
  color: var(--text);
  font: inherit;
  cursor: pointer;
}
</style>
