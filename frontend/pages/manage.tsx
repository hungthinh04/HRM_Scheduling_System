import { useState, useEffect } from 'react'
import Head from 'next/head'
import { useRouter } from 'next/router'
import Link from 'next/link'

interface Employee {
  id: number
  name: string
  email: string
  skills: string[]
}

interface Location {
  id: number
  name: string
  address: string
  capacity: number
  required_skills: string[]
}

interface Shift {
  id: number
  name: string
  start_time: string
  end_time: string
  duration_hours: number
}

export default function Manage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<'employees' | 'locations' | 'shifts'>('employees')
  const [employees, setEmployees] = useState<Employee[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  
  // Edit states
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null)
  const [editingLocation, setEditingLocation] = useState<Location | null>(null)
  const [editingShift, setEditingShift] = useState<Shift | null>(null)

  useEffect(() => {
    loadData()
    
    // Reload data when page becomes visible (after refresh)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadData(true) // Force reload to get latest data from backend
      }
    }
    
    // Also reload on focus (e.g., when switching tabs back)
    const handleFocus = () => {
      loadData(true)
    }
    
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', handleFocus)
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
    }
  }, [])

  const loadData = async (forceReload = false) => {
    try {
      // Always try loading from backend API first (source of truth)
      let empData: Employee[] = []
      let locData: Location[] = []
      let shiftData: Shift[] = []
      
      const cacheBuster = forceReload ? '?t=' + Date.now() : ''
      
      try {
        const backendBase = 'http://localhost:8000/api/data'
        const [empRes, locRes, shiftRes] = await Promise.all([
          fetch(`${backendBase}/employees.json${cacheBuster}`).catch(() => null),
          fetch(`${backendBase}/locations.json${cacheBuster}`).catch(() => null),
          fetch(`${backendBase}/shifts.json${cacheBuster}`).catch(() => null)
        ])
        
        if (empRes && empRes.ok) {
          empData = await empRes.json()
        }
        if (locRes && locRes.ok) {
          locData = await locRes.json()
        }
        if (shiftRes && shiftRes.ok) {
          shiftData = await shiftRes.json()
        }
      } catch (err) {
        console.log('Backend API not available, trying public folder...')
      }
      
      // If backend failed, try public folder as fallback
      if (empData.length === 0 || locData.length === 0 || shiftData.length === 0) {
        try {
          const [empRes2, locRes2, shiftRes2] = await Promise.all([
            fetch(`/employees.json${cacheBuster}`).catch(() => null),
            fetch(`/locations.json${cacheBuster}`).catch(() => null),
            fetch(`/shifts.json${cacheBuster}`).catch(() => null)
          ])
          
          if (empRes2 && empRes2.ok) {
            empData = await empRes2.json()
          }
          if (locRes2 && locRes2.ok) {
            locData = await locRes2.json()
          }
          if (shiftRes2 && shiftRes2.ok) {
            shiftData = await shiftRes2.json()
          }
        } catch (err) {
          console.log('Public folder files not found')
        }
      }
      
      // Set data (even if empty, user can still see the UI)
      setEmployees(empData)
      setLocations(locData)
      setShifts(shiftData)
      setLoading(false)
      
      // Show warning if no data
      if (empData.length === 0 && locData.length === 0 && shiftData.length === 0) {
        console.warn('No data found. Please run: cd backend && python copy_data_to_frontend.py')
      }
    } catch (err) {
      console.error('Failed to load data:', err)
      setLoading(false)
    }
  }

  const saveDataToBackend = async (data?: { employees?: Employee[], locations?: Location[], shifts?: Shift[] }) => {
    setSaving(true)
    try {
      // Use provided data or fallback to current state
      const dataToSave = {
        employees: data?.employees ?? employees,
        locations: data?.locations ?? locations,
        shifts: data?.shifts ?? shifts
      }
      
      const response = await fetch('http://localhost:8000/api/save-data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dataToSave)
      })
      
      const result = await response.json()
      if (result.success) {
        console.log('Data saved to backend successfully')
        return true
      } else {
        console.error('Failed to save data:', result.error)
        return false
      }
    } catch (err) {
      console.error('Error saving data:', err)
      return false
    } finally {
      setSaving(false)
    }
  }

  const saveData = async () => {
    // Check if data is empty
    if (employees.length === 0 || locations.length === 0 || shifts.length === 0) {
      alert('Please ensure you have employees, locations, and shifts data before generating schedule.')
      return
    }

    setGenerating(true)
    try {
      // First save current data to backend
      await saveDataToBackend()
      
      // Show progress message
      const progressMsg = document.createElement('div')
      progressMsg.style.cssText = 'position:fixed;top:20px;right:20px;background:#007bff;color:white;padding:20px;border-radius:8px;z-index:9999;box-shadow:0 4px 6px rgba(0,0,0,0.1);max-width:300px;'
      progressMsg.innerHTML = `
        <div style="font-weight:bold;margin-bottom:10px;">⏳ Generating Schedule...</div>
        <div style="font-size:0.9em;margin-bottom:10px;">Please wait, this may take 10-30 seconds</div>
        <div style="background:rgba(255,255,255,0.3);height:4px;border-radius:2px;overflow:hidden;">
          <div style="background:white;height:100%;width:0%;animation:pulse 1.5s infinite;" id="progress-bar"></div>
        </div>
      `
      document.body.appendChild(progressMsg)
      
      // Animate progress bar
      let progress = 0
      const progressInterval = setInterval(() => {
        progress += 10
        if (progress > 90) progress = 90
        const bar = document.getElementById('progress-bar')
        if (bar) bar.style.width = progress + '%'
      }, 1000)
      
      // Then generate schedule
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employees, locations, shifts })
      })
      
      clearInterval(progressInterval)
      const bar = document.getElementById('progress-bar')
      if (bar) bar.style.width = '100%'
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result = await response.json()
      
      progressMsg.innerHTML = '<div style="font-weight:bold;">✅ Schedule Generated!</div><div style="font-size:0.9em;margin-top:10px;">Redirecting...</div>'
      setTimeout(() => {
        document.body.removeChild(progressMsg)
        // Redirect to home page and reload to show new schedule
        window.location.href = '/?refresh=' + Date.now()
      }, 1000)
      
    } catch (err: any) {
      console.error('Generation error:', err)
      // Remove progress message if exists
      const existingMsg = document.querySelector('div[style*="position:fixed"]')
      if (existingMsg) document.body.removeChild(existingMsg)
      
      if (err.message?.includes('fetch') || err.message?.includes('NetworkError')) {
        alert('Cannot connect to backend API server.\n\nPlease start the backend server first:\n\ncd backend\npython api_server.py\n\nThen try again.')
      } else {
        alert(`Error: ${err.message || 'Unknown error'}`)
      }
      setGenerating(false)
    }
  }

  const updateEmployee = async (updated: Employee) => {
    const newEmployees = employees.map(e => e.id === updated.id ? updated : e)
    setEmployees(newEmployees)
    setEditingEmployee(null)
    // Auto-save to backend with new data
    await saveDataToBackend({ employees: newEmployees, locations, shifts })
  }

  const updateLocation = async (updated: Location) => {
    const newLocations = locations.map(l => l.id === updated.id ? updated : l)
    setLocations(newLocations)
    setEditingLocation(null)
    // Auto-save to backend with new data
    await saveDataToBackend({ employees, locations: newLocations, shifts })
  }

  const updateShift = async (updated: Shift) => {
    const newShifts = shifts.map(s => s.id === updated.id ? updated : s)
    setShifts(newShifts)
    setEditingShift(null)
    // Auto-save to backend with new data
    await saveDataToBackend({ employees, locations, shifts: newShifts })
  }

  if (loading) {
    return <div className="container"><div className="loading">Loading...</div></div>
  }

  const hasData = employees.length > 0 || locations.length > 0 || shifts.length > 0

  return (
    <>
      <Head>
        <title>Manage Data - HRM Scheduling</title>
      </Head>
      <div className="container">
        <div className="header">
          <h1>📋 Manage Data</h1>
          <p>Edit employees, locations, and shifts</p>
          {saving && (
            <div style={{ 
              marginTop: '10px', 
              padding: '10px', 
              background: '#d4edda', 
              border: '1px solid #28a745', 
              borderRadius: '5px',
              color: '#155724'
            }}>
              💾 Saving changes...
            </div>
          )}
          {!hasData && (
            <div style={{ 
              marginTop: '15px', 
              padding: '15px', 
              background: '#fff3cd', 
              border: '1px solid #ffc107', 
              borderRadius: '5px',
              color: '#856404'
            }}>
              ⚠️ No data found. Loading from backend...
              <br />
              <small>If data is still missing, please run: <code>cd backend && python copy_data_to_frontend.py</code></small>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="tabs">
          <button 
            className={activeTab === 'employees' ? 'tab-active' : 'tab'}
            onClick={() => setActiveTab('employees')}
          >
            👥 Employees ({employees.length})
          </button>
          <button 
            className={activeTab === 'locations' ? 'tab-active' : 'tab'}
            onClick={() => setActiveTab('locations')}
          >
            📍 Locations ({locations.length})
          </button>
          <button 
            className={activeTab === 'shifts' ? 'tab-active' : 'tab'}
            onClick={() => setActiveTab('shifts')}
          >
            ⏰ Shifts ({shifts.length})
          </button>
        </div>

        {/* Employees Tab */}
        {activeTab === 'employees' && (
          <div className="data-section">
            <h2>Employees ({employees.length})</h2>
            <div className="data-grid">
              {employees.map(emp => (
                <div key={emp.id} className="data-card">
                  {editingEmployee?.id === emp.id ? (
                    <EditEmployeeForm 
                      employee={editingEmployee}
                      onSave={updateEmployee}
                      onCancel={() => setEditingEmployee(null)}
                    />
                  ) : (
                    <>
                      <h3>{emp.name}</h3>
                      <p>{emp.email}</p>
                      <div className="skills">
                        {emp.skills.map(skill => (
                          <span key={skill} className="skill-badge">{skill}</span>
                        ))}
                      </div>
                      <button 
                        className="edit-btn"
                        onClick={() => setEditingEmployee(emp)}
                      >
                        ✏️ Edit
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Locations Tab */}
        {activeTab === 'locations' && (
          <div className="data-section">
            <h2>Locations ({locations.length})</h2>
            <div className="data-grid">
              {locations.map(loc => (
                <div key={loc.id} className="data-card">
                  {editingLocation?.id === loc.id ? (
                    <EditLocationForm 
                      location={editingLocation}
                      onSave={updateLocation}
                      onCancel={() => setEditingLocation(null)}
                    />
                  ) : (
                    <>
                      <h3>{loc.name}</h3>
                      <p>{loc.address}</p>
                      <p><strong>Capacity:</strong> {loc.capacity}</p>
                      <div className="skills">
                        {loc.required_skills.map(skill => (
                          <span key={skill} className="skill-badge">{skill}</span>
                        ))}
                      </div>
                      <button 
                        className="edit-btn"
                        onClick={() => setEditingLocation(loc)}
                      >
                        ✏️ Edit
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Shifts Tab */}
        {activeTab === 'shifts' && (
          <div className="data-section">
            <h2>Shifts ({shifts.length})</h2>
            <div className="data-grid">
              {shifts.map(shift => (
                <div key={shift.id} className="data-card">
                  {editingShift?.id === shift.id ? (
                    <EditShiftForm 
                      shift={editingShift}
                      onSave={updateShift}
                      onCancel={() => setEditingShift(null)}
                    />
                  ) : (
                    <>
                      <h3>{shift.name}</h3>
                      <p><strong>Time:</strong> {shift.start_time} - {shift.end_time}</p>
                      <p><strong>Duration:</strong> {shift.duration_hours} hours</p>
                      <button 
                        className="edit-btn"
                        onClick={() => setEditingShift(shift)}
                      >
                        ✏️ Edit
                      </button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="action-bar">
          <button 
            className="generate-btn"
            onClick={saveData}
            disabled={generating || saving}
          >
            {generating ? '⏳ Generating Schedule...' : '🤖 Generate Schedule with AI'}
          </button>
          <Link href="/">
            <button className="view-btn">
              📊 View Schedule
            </button>
          </Link>
        </div>
      </div>
    </>
  )
}

// Edit Forms
function EditEmployeeForm({ employee, onSave, onCancel }: { 
  employee: Employee, 
  onSave: (e: Employee) => Promise<void>,
  onCancel: () => void 
}) {
  const [form, setForm] = useState(employee)
  
  return (
    <div className="edit-form">
      <input 
        type="text" 
        value={form.name}
        onChange={e => setForm({...form, name: e.target.value})}
        placeholder="Employee Name"
      />
      <input 
        type="email" 
        value={form.email}
        onChange={e => setForm({...form, email: e.target.value})}
        placeholder="Email"
      />
      <input 
        type="text" 
        value={form.skills.join(', ')}
        onChange={e => setForm({...form, skills: e.target.value.split(',').map(s => s.trim())})}
        placeholder="Skills (comma separated)"
      />
      <div className="form-actions">
        <button onClick={() => onSave(form)} className="save-btn">💾 Save</button>
        <button onClick={onCancel} className="cancel-btn">❌ Cancel</button>
      </div>
    </div>
  )
}

function EditLocationForm({ location, onSave, onCancel }: { 
  location: Location, 
  onSave: (l: Location) => Promise<void>,
  onCancel: () => void 
}) {
  const [form, setForm] = useState(location)
  
  return (
    <div className="edit-form">
      <input 
        type="text" 
        value={form.name}
        onChange={e => setForm({...form, name: e.target.value})}
        placeholder="Location Name"
      />
      <input 
        type="text" 
        value={form.address}
        onChange={e => setForm({...form, address: e.target.value})}
        placeholder="Address"
      />
      <input 
        type="number" 
        value={form.capacity}
        onChange={e => setForm({...form, capacity: parseInt(e.target.value)})}
        placeholder="Capacity"
      />
      <input 
        type="text" 
        value={form.required_skills.join(', ')}
        onChange={e => setForm({...form, required_skills: e.target.value.split(',').map(s => s.trim())})}
        placeholder="Required skills (comma separated)"
      />
      <div className="form-actions">
        <button onClick={() => onSave(form)} className="save-btn">💾 Save</button>
        <button onClick={onCancel} className="cancel-btn">❌ Cancel</button>
      </div>
    </div>
  )
}

function EditShiftForm({ shift, onSave, onCancel }: { 
  shift: Shift, 
  onSave: (s: Shift) => Promise<void>,
  onCancel: () => void 
}) {
  const [form, setForm] = useState(shift)
  
  return (
    <div className="edit-form">
      <input 
        type="text" 
        value={form.name}
        onChange={e => setForm({...form, name: e.target.value})}
        placeholder="Shift Name"
      />
      <input 
        type="time" 
        value={form.start_time}
        onChange={e => setForm({...form, start_time: e.target.value})}
        placeholder="Start time"
      />
      <input 
        type="time" 
        value={form.end_time}
        onChange={e => setForm({...form, end_time: e.target.value})}
        placeholder="End time"
      />
      <div className="form-actions">
        <button onClick={() => onSave(form)} className="save-btn">💾 Save</button>
        <button onClick={onCancel} className="cancel-btn">❌ Cancel</button>
      </div>
    </div>
  )
}
