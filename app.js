// === KP Events Calendar ===

let allEvents = [];
let filteredEvents = [];
let calendar = null;
let map = null;
let markers = [];
let selectedEventId = null;
let currentView = 'calendar';

// --- Urgency ---
function getUrgency(startDate) {
  const days = Math.ceil((new Date(startDate) - new Date()) / 86400000);
  if (days < 0)  return { level: 'past', color: '#9ca3af', label: 'Past', days };
  if (days < 14) return { level: 'urgent', color: '#ef4444', label: `${days}d left`, days };
  if (days <= 45) return { level: 'soon', color: '#f59e0b', label: `${days}d left`, days };
  return { level: 'comfortable', color: '#22c55e', label: `${days}d left`, days };
}

function getCategoryColor(category) {
  return category === 'business' ? '#3b82f6' : '#8b5cf6';
}

function getCategoryLabel(category) {
  return category === 'business' ? 'Business' : 'End User';
}

// --- Date formatting ---
function formatDate(dateStr) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric'
  });
}

function formatDateRange(start, end) {
  if (!end || start === end) return formatDate(start);
  const s = new Date(start + 'T00:00:00');
  const e = new Date(end + 'T00:00:00');
  if (s.getMonth() === e.getMonth() && s.getFullYear() === e.getFullYear()) {
    return `${s.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}-${e.getDate()}, ${e.getFullYear()}`;
  }
  return `${formatDate(start)} - ${formatDate(end)}`;
}

// --- Load Data ---
async function loadEvents() {
  try {
    const resp = await fetch('data/events.json');
    const data = await resp.json();
    allEvents = data.events || [];
    document.getElementById('lastUpdated').textContent = `Updated: ${new Date(data.last_updated).toLocaleDateString()}`;
    applyFilters();
    initCalendar();
    initMap();
    updateStats();
  } catch (err) {
    console.error('Failed to load events:', err);
  }
}

// --- Filtering ---
function applyFilters() {
  const showEndUser = document.getElementById('filterEndUser').checked;
  const showBusiness = document.getElementById('filterBusiness').checked;
  const showComfortable = document.getElementById('filterComfortable').checked;
  const showSoon = document.getElementById('filterSoon').checked;
  const showUrgent = document.getElementById('filterUrgent').checked;
  const showPast = document.getElementById('filterPast').checked;
  const search = document.getElementById('searchInput').value.toLowerCase().trim();

  filteredEvents = allEvents.filter(ev => {
    // Category
    if (ev.category === 'end_user' && !showEndUser) return false;
    if (ev.category === 'business' && !showBusiness) return false;

    // Urgency
    const urg = getUrgency(ev.start_date);
    if (urg.level === 'comfortable' && !showComfortable) return false;
    if (urg.level === 'soon' && !showSoon) return false;
    if (urg.level === 'urgent' && !showUrgent) return false;
    if (urg.level === 'past' && !showPast) return false;

    // Search
    if (search) {
      const hay = `${ev.name} ${ev.location?.city} ${ev.location?.state} ${ev.location?.country} ${ev.description}`.toLowerCase();
      if (!hay.includes(search)) return false;
    }

    return true;
  });

  refreshCalendar();
  refreshMap();
  updateStats();
}

// --- Stats ---
function updateStats() {
  const counts = { comfortable: 0, soon: 0, urgent: 0, past: 0, total: 0 };
  filteredEvents.forEach(ev => {
    const urg = getUrgency(ev.start_date);
    counts[urg.level]++;
    counts.total++;
  });

  document.getElementById('statsBar').innerHTML = `
    <span class="stat-item"><span class="stat-count">${counts.total}</span> events shown</span>
    <span class="stat-item" style="color:var(--green)"><span class="stat-count">${counts.comfortable}</span> 45+ days</span>
    <span class="stat-item" style="color:var(--yellow)"><span class="stat-count">${counts.soon}</span> 15-45 days</span>
    <span class="stat-item" style="color:var(--red)"><span class="stat-count">${counts.urgent}</span> &lt;14 days</span>
    <span class="stat-item" style="color:var(--gray)"><span class="stat-count">${counts.past}</span> past</span>
  `;
}

// --- Calendar ---
function initCalendar() {
  const el = document.getElementById('calendar');
  calendar = new FullCalendar.Calendar(el, {
    initialView: 'dayGridMonth',
    headerToolbar: {
      left: 'prev,next today',
      center: 'title',
      right: 'dayGridMonth,dayGridWeek,listMonth'
    },
    height: '100%',
    events: buildCalendarEvents(),
    eventClick: (info) => {
      info.jsEvent.preventDefault();
      openSidebar(info.event.extendedProps.eventData);
    },
    eventContent: (arg) => {
      const ev = arg.event.extendedProps.eventData;
      const catColor = getCategoryColor(ev.category);
      return {
        html: `<div class="fc-event-main">
          <span class="event-category-dot" style="background:${catColor}"></span>
          ${arg.event.title}
        </div>`
      };
    }
  });
  calendar.render();
}

function buildCalendarEvents() {
  return filteredEvents.map(ev => {
    const urg = getUrgency(ev.start_date);
    // FullCalendar end is exclusive, so add a day
    let endDate = ev.end_date || ev.start_date;
    const end = new Date(endDate + 'T00:00:00');
    end.setDate(end.getDate() + 1);

    return {
      id: ev.id,
      title: ev.name,
      start: ev.start_date,
      end: end.toISOString().split('T')[0],
      backgroundColor: urg.color,
      textColor: urg.level === 'soon' ? '#1e293b' : '#ffffff',
      extendedProps: { eventData: ev }
    };
  });
}

function refreshCalendar() {
  if (!calendar) return;
  calendar.removeAllEvents();
  calendar.addEventSource(buildCalendarEvents());
}

// --- Map ---
function initMap() {
  map = L.map('map', {
    zoomControl: true,
    scrollWheelZoom: true
  }).setView([39.8, -98.6], 4);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 18
  }).addTo(map);

  refreshMap();
}

function refreshMap() {
  if (!map) return;

  // Remove existing markers
  markers.forEach(m => map.removeLayer(m));
  markers = [];

  filteredEvents.forEach(ev => {
    if (!ev.location?.lat || !ev.location?.lng) return;

    const urg = getUrgency(ev.start_date);
    const catColor = getCategoryColor(ev.category);
    const radius = ev.category === 'business' ? 10 : 7;

    const marker = L.circleMarker([ev.location.lat, ev.location.lng], {
      radius: radius,
      fillColor: urg.color,
      color: catColor,
      weight: 3,
      opacity: 0.9,
      fillOpacity: 0.7
    }).addTo(map);

    const dateRange = formatDateRange(ev.start_date, ev.end_date);
    marker.bindPopup(`
      <div class="popup-event-name">${ev.name}</div>
      <div class="popup-event-date">${dateRange}</div>
      <div style="margin-top:4px">${ev.location.city}, ${ev.location.state || ''} ${ev.location.country}</div>
      <div style="margin-top:6px;font-size:12px;color:var(--text-muted)">${getCategoryLabel(ev.category)} &bull; ${urg.label}</div>
      ${ev.contact?.website ? `<div style="margin-top:6px"><a href="${ev.contact.website}" target="_blank">Event Website</a></div>` : ''}
    `);

    marker.on('click', () => openSidebar(ev));
    marker.eventId = ev.id;
    markers.push(marker);
  });
}

// --- Sidebar ---
function openSidebar(ev) {
  selectedEventId = ev.id;
  const urg = getUrgency(ev.start_date);
  const dateRange = formatDateRange(ev.start_date, ev.end_date);
  const outreachLabels = {
    not_started: 'Not Started',
    contacted: 'Contacted',
    confirmed: 'Confirmed',
    declined: 'Declined'
  };

  let contactHtml = '';
  if (ev.contact) {
    if (ev.contact.email) contactHtml += `
      <div class="event-detail-section">
        <div class="event-detail-label">Email</div>
        <div class="event-detail-value"><a href="mailto:${ev.contact.email}">${ev.contact.email}</a></div>
      </div>`;
    if (ev.contact.phone) contactHtml += `
      <div class="event-detail-section">
        <div class="event-detail-label">Phone</div>
        <div class="event-detail-value"><a href="tel:${ev.contact.phone}">${ev.contact.phone}</a></div>
      </div>`;
    if (ev.contact.website) contactHtml += `
      <div class="event-detail-section">
        <div class="event-detail-label">Website</div>
        <div class="event-detail-value"><a href="${ev.contact.website}" target="_blank">${ev.contact.website}</a></div>
      </div>`;
  }

  document.getElementById('sidebarContent').innerHTML = `
    <div class="event-detail-header">
      <div class="event-detail-name">${ev.name}</div>
      <div class="event-detail-badges">
        <span class="badge badge-${ev.category === 'business' ? 'business' : 'end-user'}">${getCategoryLabel(ev.category)}</span>
        <span class="badge badge-${urg.level}">${urg.label}</span>
      </div>
    </div>

    <div class="event-detail-section">
      <div class="event-detail-label">Date</div>
      <div class="event-detail-value">${dateRange}</div>
    </div>

    <div class="event-detail-section">
      <div class="event-detail-label">Location</div>
      <div class="event-detail-value">
        ${ev.location?.venue ? ev.location.venue + '<br>' : ''}
        ${ev.location?.city || ''}${ev.location?.state ? ', ' + ev.location.state : ''} ${ev.location?.country || ''}
      </div>
    </div>

    ${contactHtml}

    ${ev.description ? `
    <div class="event-detail-section">
      <div class="event-detail-label">Description</div>
      <div class="event-detail-value">${ev.description}</div>
    </div>` : ''}

    <div class="event-detail-section">
      <div class="event-detail-label">Outreach Status</div>
      <div class="event-detail-value">
        <span class="outreach-status outreach-${ev.outreach_status || 'not_started'}">
          ${outreachLabels[ev.outreach_status || 'not_started']}
        </span>
      </div>
    </div>

    ${ev.source ? `
    <div class="event-detail-section">
      <div class="event-detail-label">Source</div>
      <div class="event-detail-value">${ev.source}${ev.source_url ? ` &bull; <a href="${ev.source_url}" target="_blank">link</a>` : ''}</div>
    </div>` : ''}

    ${ev.notes ? `
    <div class="event-detail-section">
      <div class="event-detail-label">Notes</div>
      <div class="event-detail-value">${ev.notes}</div>
    </div>` : ''}
  `;

  document.getElementById('sidebar').classList.add('open');

  // Highlight on map
  markers.forEach(m => {
    if (m.eventId === ev.id) {
      m.setStyle({ weight: 5, fillOpacity: 1 });
      m.openPopup();
    } else {
      m.setStyle({ weight: 3, fillOpacity: 0.7 });
    }
  });
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  selectedEventId = null;
  markers.forEach(m => m.setStyle({ weight: 3, fillOpacity: 0.7 }));
}

// --- View Toggle ---
function setView(view) {
  currentView = view;
  const mainContent = document.getElementById('mainContent');
  const calContainer = document.getElementById('calendarContainer');
  const mapContainer = document.getElementById('mapContainer');

  // Remove split class
  mainContent.classList.remove('split');

  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });

  if (view === 'calendar') {
    calContainer.style.display = 'block';
    mapContainer.style.display = 'none';
  } else if (view === 'map') {
    calContainer.style.display = 'none';
    mapContainer.style.display = 'block';
    setTimeout(() => map?.invalidateSize(), 100);
  } else if (view === 'split') {
    mainContent.classList.add('split');
    calContainer.style.display = 'block';
    mapContainer.style.display = 'block';
    setTimeout(() => map?.invalidateSize(), 100);
  }

  if (calendar) calendar.updateSize();
}

// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
  loadEvents();

  // View toggle
  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', () => setView(btn.dataset.view));
  });

  // Filters
  ['filterEndUser', 'filterBusiness', 'filterComfortable', 'filterSoon', 'filterUrgent', 'filterPast'].forEach(id => {
    document.getElementById(id).addEventListener('change', applyFilters);
  });

  // Search
  let searchTimeout;
  document.getElementById('searchInput').addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(applyFilters, 200);
  });

  // Sidebar close
  document.getElementById('sidebarClose').addEventListener('click', closeSidebar);
  document.getElementById('sidebarOverlay').addEventListener('click', closeSidebar);

  // Keyboard
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSidebar();
  });
});
