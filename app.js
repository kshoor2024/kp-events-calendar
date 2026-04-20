// === KP Events Calendar ===

let allEvents = [];
let filteredEvents = [];
let calendar = null;
let map = null;
let markers = [];
let selectedEventId = null;
let currentView = 'list';
let listSort = { key: 'date', dir: 'asc' };

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

// --- CSV Parser ---
function loadCSV(text) {
  const rows = [];
  let current = '', fields = [], inQuotes = false;
  for (let i = 0; i <= text.length; i++) {
    const ch = i < text.length ? text[i] : '\n';
    if (ch === '"') {
      if (inQuotes && text[i + 1] === '"') { current += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      fields.push(current); current = '';
    } else if ((ch === '\n' || ch === '\r') && !inQuotes) {
      fields.push(current);
      if (fields.length > 1) rows.push(fields.slice());
      fields = []; current = '';
      if (ch === '\r' && text[i + 1] === '\n') i++;
    } else {
      current += ch;
    }
  }
  if (rows.length < 2) return [];
  const headers = rows[0];
  return rows.slice(1).map(cols => {
    const obj = {};
    headers.forEach((h, i) => obj[h.trim()] = (cols[i] || '').trim());
    return obj;
  });
}

function csvRowToEvent(row) {
  const name = row['Event Name'] || '';
  const id = name.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim().replace(/ +/g, '-').slice(0, 60);
  const type = (row['Type'] || '').toLowerCase().includes('business') ? 'business' : 'end_user';
  const status = row['Status'] || 'Not contacted';
  const priority = row['Priority'] || 'B';
  const tags = (row['Tags'] || '').split(';').filter(Boolean);

  // Map status to outreach_status
  let outreach = 'not_started';
  if (status.toLowerCase().includes('contacted')) outreach = 'contacted';
  if (status.toLowerCase().includes('accepted') || status.toLowerCase().includes('confirmed')) outreach = 'confirmed';
  if (status.toLowerCase().includes('declined') || status.toLowerCase().includes('do not')) outreach = 'declined';
  if (status.toLowerCase().includes('archived')) outreach = 'declined';

  return {
    id,
    name,
    category: type,
    tier: priority === 'A' ? 1 : priority === 'B' ? 2 : 3,
    start_date: row['Date(s)'] || '',
    end_date: row['End Date'] || row['Date(s)'] || '',
    location: {
      venue: '',
      city: row['City'] || '',
      state: row['State'] || '',
      country: row['Country'] || 'US',
      lat: null,
      lng: null,
    },
    contact: {
      email: (row['Contact Email or IG'] || '').includes('@') && !(row['Contact Email or IG'] || '').startsWith('@') ? row['Contact Email or IG'] : '',
      phone: '',
      website: row['Source URL'] || '',
    },
    description: row['Notes'] || '',
    source: 'csv',
    source_url: row['Source URL'] || '',
    added_date: row['Date Added'] || '',
    outreach_status: outreach,
    status_raw: status,
    priority,
    tags,
    notes: row['Notes'] || '',
    consumption: row['Consumption On-Site'] || '',
    accepts_product: row['Accepts Free Product'] || '',
    event_size: row['Event Size'] || '',
  };
}

// --- Load Data ---
async function loadEvents() {
  try {
    // Try CSV first, fall back to JSON
    let loaded = false;
    try {
      const csvResp = await fetch('data/events_database.csv');
      if (csvResp.ok) {
        const text = await csvResp.text();
        const rows = loadCSV(text);
        allEvents = rows.map(csvRowToEvent).filter(e => e.name);
        loaded = true;
      }
    } catch (e) { /* fall back to JSON */ }

    if (!loaded) {
      const resp = await fetch('data/events.json');
      const data = await resp.json();
      allEvents = data.events || [];
    }

    // Geocode events without lat/lng (use a simple lookup)
    await geocodeEvents();

    loadOutreachFromLocalStorage();
    document.getElementById('lastUpdated').textContent = `Updated: ${new Date().toLocaleDateString()}`;
    applyFilters();
    initCalendar();
    initMap();
    refreshList();
    updateStats();
  } catch (err) {
    console.error('Failed to load events:', err);
  }
}

// Simple geocoding from city/state
const CITY_COORDS = {
  'los angeles,ca': [34.0522, -118.2437], 'west hollywood,ca': [34.0900, -118.3617],
  'san francisco,ca': [37.7749, -122.4194], 'oakland,ca': [37.8044, -122.2712],
  'san diego,ca': [32.7157, -117.1611], 'monterey,ca': [36.6002, -121.8947],
  'long beach,ca': [33.7701, -118.1937], 'santa rosa,ca': [38.4404, -122.7141],
  'willits,ca': [39.4096, -123.3558], 'piercy,ca': [39.9663, -123.7944],
  'topanga,ca': [34.0397, -118.6026], 'san bernardino,ca': [34.1083, -117.2898],
  'sacramento,ca': [38.5816, -121.4944], 'humboldt county,ca': [40.7440, -123.8695],
  'denver,co': [39.7392, -104.9903], 'morrison,co': [39.6536, -105.1911],
  'las vegas,nv': [36.1699, -115.1398], 'phoenix,az': [33.4484, -112.0740],
  'tempe,az': [33.4255, -111.9400], 'seattle,wa': [47.6062, -122.3321],
  'redmond,or': [44.2726, -121.1739], 'portland,or': [45.5152, -122.6784],
  'new york,ny': [40.7128, -74.0060], 'boston,ma': [42.3601, -71.0589],
  'detroit,mi': [42.3314, -83.0458], 'ann arbor,mi': [42.2808, -83.7430],
  'chicago,il': [41.8781, -87.6298], 'atlantic city,nj': [39.3643, -74.4229],
  'washington,dc': [38.9072, -77.0369], 'st. petersburg,fl': [27.7676, -82.6403],
  'st. louis,mo': [38.6270, -90.1994], 'kansas city,mo': [39.0997, -94.5786],
  'berlin,de': [52.5200, 13.4050], 'bilbao,es': [43.2630, -2.9350],
  'dortmund,de': [51.5136, 7.4653], 'bangkok,th': [13.7563, 100.5018],
  'toronto,on': [43.6532, -79.3832], 'johannesburg,za': [-26.2041, 28.0473],
  'medellin,co': [6.2476, -75.5658],
};

async function geocodeEvents() {
  for (const ev of allEvents) {
    if (ev.location.lat && ev.location.lng) continue;
    const key = `${ev.location.city},${ev.location.state}`.toLowerCase();
    const coords = CITY_COORDS[key];
    if (coords) {
      ev.location.lat = coords[0];
      ev.location.lng = coords[1];
    }
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
  refreshList();
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
let heatmapLayer = null;
let heatmapVisible = false;

// Cannabis legality by state (as of 2026)
// rec = recreational legal, med = medical only, none = illegal/CBD only
const STATE_CANNABIS_STATUS = {
  'Alabama':'med','Alaska':'rec','Arizona':'rec','Arkansas':'med','California':'rec',
  'Colorado':'rec','Connecticut':'rec','Delaware':'rec','Florida':'med','Georgia':'none',
  'Hawaii':'rec','Idaho':'none','Illinois':'rec','Indiana':'none','Iowa':'none',
  'Kansas':'none','Kentucky':'med','Louisiana':'med','Maine':'rec','Maryland':'rec',
  'Massachusetts':'rec','Michigan':'rec','Minnesota':'rec','Mississippi':'med',
  'Missouri':'rec','Montana':'rec','Nebraska':'rec','Nevada':'rec','New Hampshire':'med',
  'New Jersey':'rec','New Mexico':'rec','New York':'rec','North Carolina':'none',
  'North Dakota':'med','Ohio':'rec','Oklahoma':'med','Oregon':'rec','Pennsylvania':'med',
  'Rhode Island':'rec','South Carolina':'none','South Dakota':'med','Tennessee':'none',
  'Texas':'none','Utah':'med','Vermont':'rec','Virginia':'rec','Washington':'rec',
  'West Virginia':'med','Wisconsin':'none','Wyoming':'none','District of Columbia':'rec'
};

const LEGALITY_COLORS = {
  'rec': 'rgba(34, 197, 94, 0.25)',    // green
  'med': 'rgba(245, 158, 11, 0.2)',    // yellow
  'none': 'rgba(239, 68, 68, 0.12)'    // red
};

function initMap() {
  map = L.map('map', {
    zoomControl: true,
    scrollWheelZoom: true
  }).setView([39.8, -98.6], 4);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    maxZoom: 18
  }).addTo(map);

  // Add heatmap toggle control
  const HeatmapControl = L.Control.extend({
    options: { position: 'topright' },
    onAdd: function() {
      const div = L.DomUtil.create('div', 'leaflet-bar heatmap-control');
      div.innerHTML = `<a href="#" title="Toggle cannabis legality overlay" id="heatmapToggle">&#x1f33f;</a>`;
      div.querySelector('a').addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleHeatmap();
      });
      return div;
    }
  });
  new HeatmapControl().addTo(map);

  // Load GeoJSON for states, then auto-enable if URL hash
  loadStateGeoJSON().then(() => {
    if (window.location.hash === '#heatmap') toggleHeatmap();
  });

  refreshMap();
}

async function loadStateGeoJSON() {
  try {
    const resp = await fetch('data/us-states.geo.json');
    if (!resp.ok) return;
    const geojson = await resp.json();

    heatmapLayer = L.geoJSON(geojson, {
      style: (feature) => {
        const name = feature.properties.NAME || feature.properties.name;
        const status = STATE_CANNABIS_STATUS[name] || 'none';
        return {
          fillColor: LEGALITY_COLORS[status],
          fillOpacity: 1,
          color: status === 'rec' ? 'rgba(34,197,94,0.4)' : status === 'med' ? 'rgba(245,158,11,0.3)' : 'rgba(239,68,68,0.15)',
          weight: 1
        };
      },
      onEachFeature: (feature, layer) => {
        const name = feature.properties.NAME || feature.properties.name;
        const status = STATE_CANNABIS_STATUS[abbr] || 'none';
        const statusLabel = status === 'rec' ? 'Recreational Legal' : status === 'med' ? 'Medical Only' : 'Not Legal';
        layer.bindTooltip(`<strong>${name}</strong><br>${statusLabel}`, {
          sticky: true,
          className: 'state-tooltip'
        });
      }
    });
  } catch (e) {
    console.log('State GeoJSON not loaded:', e.message);
  }
}

function toggleHeatmap() {
  if (!heatmapLayer) return;
  heatmapVisible = !heatmapVisible;
  if (heatmapVisible) {
    heatmapLayer.addTo(map);
    heatmapLayer.bringToBack();
    document.getElementById('heatmapToggle')?.classList.add('active');
  } else {
    map.removeLayer(heatmapLayer);
    document.getElementById('heatmapToggle')?.classList.remove('active');
  }
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

// --- List/Table View ---
function refreshList() {
  const tbody = document.getElementById('eventsTableBody');
  if (!tbody) return;

  // Sort filtered events — past events always go to the bottom
  const sorted = [...filteredEvents].sort((a, b) => {
    const aIsPast = getUrgency(a.start_date).level === 'past';
    const bIsPast = getUrgency(b.start_date).level === 'past';

    // Past events sink to bottom regardless of sort
    if (aIsPast && !bIsPast) return 1;
    if (!aIsPast && bIsPast) return -1;

    let va, vb;
    switch (listSort.key) {
      case 'name':
        va = a.name.toLowerCase(); vb = b.name.toLowerCase();
        break;
      case 'category':
        va = a.category; vb = b.category;
        break;
      case 'date':
        va = a.start_date || '9999'; vb = b.start_date || '9999';
        break;
      case 'location':
        va = (a.location?.city || '').toLowerCase();
        vb = (b.location?.city || '').toLowerCase();
        break;
      case 'tier':
        va = a.tier || 9; vb = b.tier || 9;
        break;
      case 'outreach':
        va = a.outreach_status || 'not_started';
        vb = b.outreach_status || 'not_started';
        break;
      case 'urgency':
        va = getUrgency(a.start_date).days;
        vb = getUrgency(b.start_date).days;
        break;
      default:
        va = a.start_date || '9999'; vb = b.start_date || '9999';
    }
    if (va < vb) return listSort.dir === 'asc' ? -1 : 1;
    if (va > vb) return listSort.dir === 'asc' ? 1 : -1;
    return 0;
  });

  const outreachLabels = {
    not_started: 'Not Started',
    contacted: 'Contacted',
    confirmed: 'Confirmed',
    declined: 'Declined'
  };

  tbody.innerHTML = sorted.map(ev => {
    const urg = getUrgency(ev.start_date);
    const dateRange = formatDateRange(ev.start_date, ev.end_date);
    const loc = ev.location || {};
    const locationStr = [loc.city, loc.state].filter(Boolean).join(', ') + (loc.country && loc.country !== 'US' ? ` ${loc.country}` : '');
    const contact = ev.contact || {};
    const outreach = ev.outreach_status || 'not_started';

    let contactHtml = '';
    if (contact.email) contactHtml = `<a href="mailto:${contact.email}">${contact.email}</a>`;
    else if (contact.phone) contactHtml = `<a href="tel:${contact.phone}">${contact.phone}</a>`;
    else if (contact.website) contactHtml = `<a href="${contact.website}" target="_blank">Website</a>`;

    return `<tr data-event-id="${ev.id}" class="${selectedEventId === ev.id ? 'selected' : ''}">
      <td>
        <div class="table-urgency">
          <span class="table-urgency-dot" style="background:${urg.color}"></span>
          <span class="table-urgency-label">${urg.label}</span>
        </div>
      </td>
      <td>
        <div class="table-event-name">${ev.name}</div>
        ${ev.description ? `<div class="table-event-desc">${ev.description}</div>` : ''}
      </td>
      <td><span class="table-category ${ev.category}">${getCategoryLabel(ev.category)}</span></td>
      <td><span class="table-tier tier-${ev.tier || 1}">T${ev.tier || 1}</span></td>
      <td style="white-space:nowrap">${dateRange}</td>
      <td class="table-location">${locationStr}</td>
      <td class="table-contact">${contactHtml}</td>
      <td>
        <select class="outreach-select ${outreach}" data-event-id="${ev.id}">
          <option value="not_started" ${outreach === 'not_started' ? 'selected' : ''}>Not Started</option>
          <option value="contacted" ${outreach === 'contacted' ? 'selected' : ''}>Contacted</option>
          <option value="confirmed" ${outreach === 'confirmed' ? 'selected' : ''}>Confirmed</option>
          <option value="declined" ${outreach === 'declined' ? 'selected' : ''}>Declined</option>
        </select>
      </td>
    </tr>`;
  }).join('');

  // Outreach dropdown handler
  tbody.querySelectorAll('.outreach-select').forEach(select => {
    select.addEventListener('change', (e) => {
      e.stopPropagation();
      const id = select.dataset.eventId;
      const newStatus = select.value;
      updateOutreachStatus(id, newStatus);
      // Update select styling
      select.className = `outreach-select ${newStatus}`;
    });
    // Prevent row click when interacting with dropdown
    select.addEventListener('click', (e) => e.stopPropagation());
  });

  // Row click handler
  tbody.querySelectorAll('tr').forEach(row => {
    row.addEventListener('click', () => {
      const id = row.dataset.eventId;
      const ev = filteredEvents.find(e => e.id === id);
      if (ev) openSidebar(ev);
    });
  });

  // Update sort header indicators
  document.querySelectorAll('.th-sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.sort === listSort.key) {
      th.classList.add(listSort.dir === 'asc' ? 'sort-asc' : 'sort-desc');
    }
  });
}

// --- Outreach Status Update ---
function updateOutreachStatus(eventId, newStatus) {
  // Update in allEvents
  const ev = allEvents.find(e => e.id === eventId);
  if (ev) {
    ev.outreach_status = newStatus;
    // Save to localStorage so changes persist across page loads
    saveOutreachToLocalStorage();
    // If sidebar is open for this event, refresh it
    if (selectedEventId === eventId) {
      openSidebar(ev);
    }
  }
}

function saveOutreachToLocalStorage() {
  const outreachMap = {};
  allEvents.forEach(ev => {
    if (ev.outreach_status && ev.outreach_status !== 'not_started') {
      outreachMap[ev.id] = ev.outreach_status;
    }
  });
  localStorage.setItem('kp_outreach_status', JSON.stringify(outreachMap));
}

function loadOutreachFromLocalStorage() {
  try {
    const saved = JSON.parse(localStorage.getItem('kp_outreach_status') || '{}');
    allEvents.forEach(ev => {
      if (saved[ev.id]) {
        ev.outreach_status = saved[ev.id];
      }
    });
  } catch (e) {
    // ignore parse errors
  }
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
  const listContainer = document.getElementById('listContainer');
  const mapContainer = document.getElementById('mapContainer');

  // Remove split class
  mainContent.classList.remove('split');

  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });

  // Hide all first
  calContainer.style.display = 'none';
  listContainer.style.display = 'none';
  mapContainer.style.display = 'none';

  if (view === 'calendar') {
    calContainer.style.display = 'block';
  } else if (view === 'list') {
    listContainer.style.display = 'block';
    refreshList();
  } else if (view === 'map') {
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

  // Table sort headers
  document.querySelectorAll('.th-sortable').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (listSort.key === key) {
        listSort.dir = listSort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        listSort.key = key;
        listSort.dir = 'asc';
      }
      refreshList();
    });
  });

  // Sidebar close
  document.getElementById('sidebarClose').addEventListener('click', closeSidebar);
  document.getElementById('sidebarOverlay').addEventListener('click', closeSidebar);

  // Keyboard
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSidebar();
  });
});
