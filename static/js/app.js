function foodViseurApp() {
  return {
    page: 'dashboard',

    goals: { calories: 2000, proteins: 150, carbs: 250, fats: 70 },
    today: { total_calories: 0, total_proteins: 0, total_carbs: 0, total_fats: 0, meals: [] },
    journalDate: new Date().toISOString().split('T')[0],

    // Recherche
    searchQuery: '',
    searchResults: [],
    searchDebounce: null,
    selectedFood: null,
    addQty: 100,
    addMealType: 'dejeuner',
    searching: false,
    searchSource: 'auto',

    // Aliments récents
    recentFoods: [],

    // Ajout manuel
    showManualForm: false,
    manualForm: { name: '', brand: '', calories_100g: 0, proteins_100g: 0, carbs_100g: 0, fats_100g: 0 },

    // Scanner
    scannerActive: false,
    scannerError: '',
    scannerResult: null,
    scanQty: 100,
    scanMealType: 'dejeuner',
    barcodeDetector: null,
    zxingReader: null,
    videoStream: null,
    scanInterval: null,
    scanContinuous: false, // mode scan en continu après ajout

    // Modale édition
    editEntry: null,
    editQty: 0,
    editMealType: 'dejeuner',
    editNotes: '',

    // Toast
    toast: { show: false, msg: '', type: 'success' },

    // Réglages
    settingsForm: { calories: 2000, proteins: 150, carbs: 250, fats: 70 },

    mealTypes: [
      { key: 'petit_dej', label: 'Petit-déjeuner', short: 'Petit-déj', emoji: '🌅' },
      { key: 'dejeuner',  label: 'Déjeuner',       short: 'Déjeuner',  emoji: '☀️' },
      { key: 'diner',     label: 'Dîner',           short: 'Dîner',     emoji: '🌙' },
      { key: 'encas',     label: 'En-cas',          short: 'En-cas',    emoji: '🍎' },
    ],

    async init() {
      await this.loadGoals();
      await this.loadToday();
      await this.loadRecentFoods();
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js').catch(() => {});
      }
    },

    async api(method, path, body = null) {
      const opts = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(path, opts);
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    },

    // ─── Goals ─────────────────────────────────────────────────────
    async loadGoals() {
      try { this.goals = await this.api('GET', '/api/goals/'); this.settingsForm = { ...this.goals }; }
      catch (e) { console.error(e); }
    },

    async saveGoals() {
      try {
        this.goals = await this.api('PUT', '/api/goals/', this.settingsForm);
        this.showToast('Objectifs enregistrés ✓');
        await this.loadToday();
      } catch (e) { this.showToast('Erreur lors de la sauvegarde', 'error'); }
    },

    // ─── Journal ───────────────────────────────────────────────────
    async loadToday() {
      try { this.today = await this.api('GET', `/api/meals/summary/${this.journalDate}`); }
      catch (e) { console.error(e); }
    },

    async changeDate(delta) {
      const d = new Date(this.journalDate);
      d.setDate(d.getDate() + delta);
      this.journalDate = d.toISOString().split('T')[0];
      await this.loadToday();
    },

    isToday() { return this.journalDate === new Date().toISOString().split('T')[0]; },

    formatDate(dateStr) {
      const d = new Date(dateStr + 'T00:00:00');
      return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
    },

    getMealGroup(key) {
      if (!this.today.meals) return { entries: [], total_calories: 0, total_proteins: 0, total_carbs: 0, total_fats: 0 };
      return this.today.meals.find(m => m.meal_type === key)
        || { entries: [], total_calories: 0, total_proteins: 0, total_carbs: 0, total_fats: 0 };
    },

    totalEntries() {
      if (!this.today.meals) return 0;
      return this.today.meals.reduce((s, m) => s + m.entries.length, 0);
    },

    async deleteEntry(id) {
      try { await this.api('DELETE', `/api/meals/${id}`); await this.loadToday(); this.showToast('Supprimé'); }
      catch (e) { this.showToast('Erreur', 'error'); }
    },

    openEditModal(entry) {
      this.editEntry = JSON.parse(JSON.stringify(entry));
      this.editQty = entry.quantity_g;
      this.editMealType = entry.meal_type;
      this.editNotes = entry.notes || '';
    },

    closeEditModal() { this.editEntry = null; },

    get editPreview() {
      if (!this.editEntry) return { calories: 0, proteins: 0, carbs: 0, fats: 0 };
      const r = (parseFloat(this.editQty) || 0) / 100;
      return {
        calories: Math.round(this.editEntry.calories_100g * r * 10) / 10,
        proteins: Math.round(this.editEntry.proteins_100g * r * 10) / 10,
        carbs:    Math.round(this.editEntry.carbs_100g    * r * 10) / 10,
        fats:     Math.round(this.editEntry.fats_100g     * r * 10) / 10,
      };
    },

    async saveEditModal() {
      if (!this.editEntry) return;
      try {
        await this.api('PATCH', `/api/meals/${this.editEntry.id}`, {
          quantity_g: parseFloat(this.editQty),
          meal_type: this.editMealType,
          notes: this.editNotes,
        });
        await this.loadToday();
        this.closeEditModal();
        this.showToast('Mis à jour ✓');
      } catch (e) { this.showToast('Erreur', 'error'); }
    },

    // ─── Aliments récents ──────────────────────────────────────────
    async loadRecentFoods() {
      try { this.recentFoods = await this.api('GET', '/api/food/recent'); }
      catch (e) { this.recentFoods = []; }
    },

    selectRecentFood(recent) {
      this.selectedFood = {
        id: recent.id,
        name: recent.name,
        brand: recent.brand,
        calories_100g: recent.calories_100g,
        proteins_100g: recent.proteins_100g,
        carbs_100g: recent.carbs_100g,
        fats_100g: recent.fats_100g,
        is_custom: recent.is_custom,
      };
      this.addQty = recent.last_quantity_g || 100;
      this.showManualForm = false;
    },

    async deleteCustomFood(foodId) {
      try {
        await this.api('DELETE', `/api/food/custom/${foodId}`);
        await this.loadRecentFoods();
        this.showToast('Aliment supprimé');
      } catch (e) { this.showToast('Erreur lors de la suppression', 'error'); }
    },

    // ─── Recherche ─────────────────────────────────────────────────
    onSearchInput() {
      clearTimeout(this.searchDebounce);
      if (this.searchQuery.length < 2) { this.searchResults = []; return; }
      this.searchSource = 'auto';
      this.searchDebounce = setTimeout(() => this.doSearch(), 300);
    },

    async doSearch(source = null) {
      this.searching = true;
      const src = source || this.searchSource;
      try {
        const resp = await fetch(`/api/food/search?q=${encodeURIComponent(this.searchQuery)}&source=${src}`);
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          this.showToast(err.detail || `Erreur ${resp.status}`, 'error');
          this.searchResults = [];
          return;
        }
        this.searchResults = await resp.json();
        this.searchSource = src;
      } catch (e) {
        this.showToast('Erreur réseau', 'error');
        this.searchResults = [];
      } finally {
        this.searching = false;
      }
    },

    async forceOffSearch() {
      this.searchSource = 'off';
      await this.doSearch('off');
    },

    selectFood(food) {
      this.selectedFood = food;
      this.addQty = 100;
      this.showManualForm = false;
    },

    clearSearch() {
      this.searchQuery = '';
      this.searchResults = [];
      this.selectedFood = null;
      this.showManualForm = false;
      this.searchSource = 'auto';
    },

    // Saisie manuelle
    openManualForm() {
      this.showManualForm = true;
      this.selectedFood = null;
      this.searchResults = [];
      this.manualForm = { name: '', brand: '', calories_100g: 0, proteins_100g: 0, carbs_100g: 0, fats_100g: 0 };
      this.addQty = 100;
    },

    async confirmManualFood() {
      if (!this.manualForm.name.trim()) { this.showToast('Le nom est obligatoire', 'error'); return; }
      const foodData = {
        name: this.manualForm.name.trim(),
        brand: this.manualForm.brand.trim() || null,
        calories_100g: parseFloat(this.manualForm.calories_100g) || 0,
        proteins_100g: parseFloat(this.manualForm.proteins_100g) || 0,
        carbs_100g:    parseFloat(this.manualForm.carbs_100g)    || 0,
        fats_100g:     parseFloat(this.manualForm.fats_100g)     || 0,
      };
      // Persister en base
      try {
        const saved = await this.api('POST', '/api/food/custom', foodData);
        this.selectedFood = saved;
      } catch (e) {
        // Fallback : garder local si erreur
        this.selectedFood = { id: null, ...foodData };
      }
      this.showManualForm = false;
    },

    async addFoodToJournal() {
      if (!this.selectedFood || !this.addQty) return;
      try {
        await this.api('POST', '/api/meals/', {
          food_name: this.selectedFood.name,
          brand: this.selectedFood.brand,
          quantity_g: parseFloat(this.addQty),
          meal_type: this.addMealType,
          calories_100g: this.selectedFood.calories_100g,
          proteins_100g: this.selectedFood.proteins_100g,
          carbs_100g: this.selectedFood.carbs_100g,
          fats_100g: this.selectedFood.fats_100g,
          food_cache_id: this.selectedFood.id,
        });
        await this.loadToday();
        await this.loadRecentFoods();
        this.clearSearch();
        this.showToast('Ajouté ✓');
        this.page = 'journal';
      } catch (e) { this.showToast("Erreur lors de l'ajout", 'error'); }
    },

    calcMacro(food, qty, macro) {
      if (!food) return 0;
      return Math.round(food[macro + '_100g'] * (parseFloat(qty) || 0) / 100 * 10) / 10;
    },

    get scanPreview() {
      const food = this.scannerResult?.food;
      if (!food) return { calories: 0, proteins: 0, carbs: 0, fats: 0 };
      const r = (parseFloat(this.scanQty) || 0) / 100;
      return {
        calories: Math.round(food.calories_100g * r * 10) / 10,
        proteins: Math.round(food.proteins_100g * r * 10) / 10,
        carbs:    Math.round(food.carbs_100g    * r * 10) / 10,
        fats:     Math.round(food.fats_100g     * r * 10) / 10,
      };
    },

    // ─── Scanner ───────────────────────────────────────────────────
    isSecureContext() { return window.isSecureContext; },

    async startScanner() {
      this.scannerActive = true;
      this.scannerError = '';
      this.scannerResult = null;
      this.scanQty = 100;

      await this.$nextTick();
      const video = document.getElementById('scanner-video');
      if (!video) return;

      try {
        this.videoStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
        });
        video.srcObject = this.videoStream;
        await video.play();
      } catch (e) {
        this.scannerError = "Impossible d'accéder à la caméra : " + e.message;
        return;
      }

      if ('BarcodeDetector' in window) {
        try {
          this.barcodeDetector = new BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e'] });
          this.scanInterval = setInterval(() => this.detectBarcode(video), 400);
          return;
        } catch (e) {}
      }

      try {
        const { BrowserMultiFormatReader } = await import('https://unpkg.com/@zxing/browser@0.1.4/esm/index.js');
        this.zxingReader = new BrowserMultiFormatReader();
        this.zxingReader.decodeFromVideoElement(video, (result) => {
          if (result) this.onBarcodeDetected(result.getText());
        });
      } catch (e) {
        this.scannerError = 'Scanner non disponible. Utilisez la recherche textuelle.';
      }
    },

    async detectBarcode(video) {
      if (!this.barcodeDetector || !video) return;
      try {
        const barcodes = await this.barcodeDetector.detect(video);
        if (barcodes.length > 0) this.onBarcodeDetected(barcodes[0].rawValue);
      } catch (e) {}
    },

    async onBarcodeDetected(barcode) {
      if (this.scannerResult) return;
      // Pause caméra mais ne pas la fermer (mode continu)
      clearInterval(this.scanInterval);
      if (this.zxingReader) { try { this.zxingReader.reset(); } catch (e) {} this.zxingReader = null; }
      this.scannerActive = false;
      this.scannerResult = { barcode, loading: true, food: null, error: null };
      try {
        const food = await this.api('GET', `/api/food/barcode/${barcode}`);
        this.scannerResult = { barcode, loading: false, food, error: null };
        this.scanQty = 100;
      } catch (e) {
        this.scannerResult = { barcode, loading: false, food: null, error: 'Produit non trouvé dans Open Food Facts' };
      }
    },

    stopScanner() {
      clearInterval(this.scanInterval);
      if (this.zxingReader) { try { this.zxingReader.reset(); } catch (e) {} this.zxingReader = null; }
      if (this.videoStream) { this.videoStream.getTracks().forEach(t => t.stop()); this.videoStream = null; }
      this.scannerActive = false;
    },

    async addScannedFood() {
      const food = this.scannerResult?.food;
      if (!food) return;
      try {
        await this.api('POST', '/api/meals/', {
          food_name: food.name,
          brand: food.brand,
          quantity_g: parseFloat(this.scanQty),
          meal_type: this.scanMealType,
          calories_100g: food.calories_100g,
          proteins_100g: food.proteins_100g,
          carbs_100g: food.carbs_100g,
          fats_100g: food.fats_100g,
          food_cache_id: food.id,
        });
        await this.loadToday();
        await this.loadRecentFoods();
        this.scannerResult = null;
        this.showToast('Ajouté ✓ — Scanner prêt');
        // Relancer le scanner automatiquement
        await this.startScanner();
      } catch (e) { this.showToast("Erreur lors de l'ajout", 'error'); }
    },

    // ─── Cercles ───────────────────────────────────────────────────
    circleProgress(consumed, goal) { if (!goal) return 0; return Math.min(consumed / goal, 1); },
    circleDash(consumed, goal) {
      const circ = 2 * Math.PI * 54;
      return `${this.circleProgress(consumed, goal) * circ} ${circ}`;
    },
    circleColor(consumed, goal) {
      const p = this.circleProgress(consumed, goal);
      if (p >= 1) return '#ef4444';
      if (p >= 0.85) return '#f59e0b';
      return '#10b981';
    },

    // ─── Toast ─────────────────────────────────────────────────────
    showToast(msg, type = 'success') {
      this.toast = { show: true, msg, type };
      setTimeout(() => { this.toast.show = false; }, 2800);
    },
  };
}
