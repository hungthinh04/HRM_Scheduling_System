import { useState, useEffect } from 'react'
import Head from 'next/head'

interface ScheduleAssignment {
  employee_id: number
  employee_name: string
  date: string
  location_id: number
  location_name: string
  shift_id: number
  shift_name: string
  start_time: string
  end_time: string
}

interface ScheduleData {
  status: string
  solver_status: string
  generated_at: string
  dates: string[]
  employees: Array<{ id: number; name: string; email: string }>
  locations: Array<{ id: number; name: string; address: string }>
  shifts: Array<{ id: number; name: string; start_time: string; end_time: string }>
  schedule: ScheduleAssignment[]
  statistics: {
    total_assignments: number
    min_shifts_per_employee: number
    max_shifts_per_employee: number
    avg_shifts_per_employee: number
    shifts_per_employee: Record<string, number>
    shifts_per_location: Record<string, number>
    shifts_per_day: Record<string, number>
    shifts_per_type: Record<string, number>
    load_balance_score?: number
    location_diversity?: Record<string, number>
    employees_multi_location?: number
    location_diversity_rate?: number
    avg_locations_per_employee?: number
    avg_shift_diversity?: number
    conflicts_detected?: number
    optimization_summary?: {
      fairness: { min_shifts: number; max_shifts: number; variance: number; score: number }
      load_balancing: { score: number; coefficient_of_variation: number }
      location_distribution: { multi_location_employees: number; diversity_rate: number; avg_per_employee: number }
    }
  }
  ai_analysis?: {
    fairness_score: number
    fairness_analysis: string
    insights: string
    optimization_suggestions: string
    schedule_explanation: string
  }
}

export default function Home() {
  const [scheduleData, setScheduleData] = useState<ScheduleData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  
  // Filters
  const [selectedDate, setSelectedDate] = useState<string>('all')
  const [selectedLocation, setSelectedLocation] = useState<string>('all')
  const [selectedEmployee, setSelectedEmployee] = useState<string>('all')
  const [selectedShift, setSelectedShift] = useState<string>('all')
  
  // Pagination
  const [currentPage, setCurrentPage] = useState<number>(1)
  const itemsPerPage = 20

  useEffect(() => {
    // Load schedule data from public folder
    fetch('/schedule_with_ai.json')
      .then(res => {
        if (!res.ok) {
          // Try loading without AI analysis
          return fetch('/schedule.json')
        }
        return res
      })
      .then(res => res.json())
      .then(data => {
        setScheduleData(data)
        setLoading(false)
      })
      .catch(err => {
        setError('Failed to load schedule data. Please make sure schedule.json exists in the public folder.')
        setLoading(false)
        console.error(err)
      })
  }, [])

  // Reset to page 1 when filters change (must be before early returns)
  useEffect(() => {
    setCurrentPage(1)
  }, [selectedDate, selectedLocation, selectedEmployee, selectedShift])

  const handleRegenerate = async () => {
    setGenerating(true)
    try {
      // Call backend API to regenerate schedule
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (response.ok) {
        const result = await response.json()
        if (result.success) {
          // Reload page to get new schedule with cache busting
          window.location.href = '/?refresh=' + Date.now()
        } else {
          alert(`Failed to regenerate schedule: ${result.error || 'Unknown error'}`)
          setGenerating(false)
        }
      } else {
        alert('Failed to regenerate schedule. Please check backend server.')
        setGenerating(false)
      }
    } catch (err: any) {
      console.error('Regenerate error:', err)
      if (err.message?.includes('fetch') || err.message?.includes('NetworkError')) {
        alert('Cannot connect to backend API server.\n\nPlease start the backend server first:\n\ncd backend\npython api_server.py\n\nThen try again.')
      } else {
        alert(`Error: ${err.message || 'Unknown error'}`)
      }
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <div className="loading">Loading schedule data...</div>
      </div>
    )
  }

  if (error || !scheduleData) {
    return (
      <div className="container">
        <div className="error">
          {error || 'No schedule data available'}
        </div>
      </div>
    )
  }

  // Filter schedule
  const filteredSchedule = scheduleData.schedule.filter(assignment => {
    if (selectedDate !== 'all' && assignment.date !== selectedDate) return false
    if (selectedLocation !== 'all' && assignment.location_id.toString() !== selectedLocation) return false
    if (selectedEmployee !== 'all' && assignment.employee_id.toString() !== selectedEmployee) return false
    if (selectedShift !== 'all' && assignment.shift_id.toString() !== selectedShift) return false
    return true
  })

  // Sort by date: newest first (descending)
  const sortedSchedule = [...filteredSchedule].sort((a, b) => {
    const dateA = new Date(a.date).getTime()
    const dateB = new Date(b.date).getTime()
    return dateB - dateA // Descending: newest first
  })

  // Pagination calculations (after sorting)
  const totalItems = sortedSchedule.length
  const totalPages = Math.ceil(totalItems / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const endIndex = startIndex + itemsPerPage
  const paginatedSchedule = sortedSchedule.slice(startIndex, endIndex)

  const getShiftBadgeClass = (shiftName: string) => {
    if (shiftName.toLowerCase().includes('morning')) return 'shift-morning'
    if (shiftName.toLowerCase().includes('afternoon')) return 'shift-afternoon'
    if (shiftName.toLowerCase().includes('evening')) return 'shift-evening'
    return ''
  }

  return (
    <>
      <Head>
        <title>HRM Scheduling System</title>
        <meta name="description" content="Employee Scheduling System with AI Integration" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="container">
        <div className="header">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h1>📅 HRM Scheduling System</h1>
              <p>AI-Powered Employee Shift Management</p>
              {scheduleData.generated_at && (
                <p style={{ marginTop: '5px', fontSize: '0.9rem' }}>
                  Generated: {new Date(scheduleData.generated_at).toLocaleString()}
                </p>
              )}
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button 
                className="nav-btn"
                onClick={() => window.location.href = '/manage'}
                style={{ padding: '10px 20px', background: '#fff', color: '#667eea', border: '2px solid #fff', borderRadius: '5px', cursor: 'pointer' }}
              >
                ✏️ Manage Data
              </button>
              <button 
                className="generate-btn-main"
                onClick={handleRegenerate}
                disabled={generating}
                style={{ padding: '10px 20px', background: '#667eea', color: '#fff', border: 'none', borderRadius: '5px', cursor: generating ? 'not-allowed' : 'pointer', opacity: generating ? 0.7 : 1 }}
              >
                {generating ? '⏳ Regenerating...' : '🔄 Regenerate Schedule'}
              </button>
            </div>
          </div>
        </div>

        {/* Basic Statistics */}
        <div className="stats-grid">
          <div className="stat-card">
            <h3>Total Assignments</h3>
            <div className="value">{scheduleData.statistics.total_assignments}</div>
          </div>
          <div className="stat-card">
            <h3>Employees</h3>
            <div className="value">{scheduleData.employees.length}</div>
          </div>
          <div className="stat-card">
            <h3>Locations</h3>
            <div className="value">{scheduleData.locations.length}</div>
          </div>
          <div className="stat-card">
            <h3>Schedule Period</h3>
            <div className="value">{scheduleData.dates.length} days</div>
          </div>
          <div className="stat-card">
            <h3>Min Shifts/Employee</h3>
            <div className="value">{scheduleData.statistics.min_shifts_per_employee}</div>
          </div>
          <div className="stat-card">
            <h3>Max Shifts/Employee</h3>
            <div className="value">{scheduleData.statistics.max_shifts_per_employee}</div>
          </div>
          <div className="stat-card">
            <h3>Avg Shifts/Employee</h3>
            <div className="value">{scheduleData.statistics.avg_shifts_per_employee.toFixed(1)}</div>
          </div>
          <div className="stat-card">
            <h3>Solver Status</h3>
            <div className="value" style={{ fontSize: '1rem' }}>{scheduleData.solver_status}</div>
          </div>
        </div>

        {/* Optimization Metrics */}
        {scheduleData.statistics.optimization_summary && (
          <div className="ai-analysis" style={{ marginTop: '20px' }}>
            <h2>📊 Optimization Metrics</h2>
            
            <div className="stats-grid" style={{ marginTop: '20px' }}>
              <div className="stat-card" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
                <h3 style={{ color: 'rgba(255,255,255,0.9)' }}>Load Balance Score</h3>
                <div className="value" style={{ color: 'white', fontSize: '2.5rem' }}>
                  {scheduleData.statistics.load_balance_score?.toFixed(1) || 'N/A'}/100
                </div>
                <p style={{ fontSize: '0.85rem', marginTop: '8px', opacity: 0.9 }}>
                  CV: {scheduleData.statistics.optimization_summary.load_balancing.coefficient_of_variation.toFixed(4)}
                </p>
              </div>
              
              <div className="stat-card" style={{ background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', color: 'white' }}>
                <h3 style={{ color: 'rgba(255,255,255,0.9)' }}>Location Diversity</h3>
                <div className="value" style={{ color: 'white', fontSize: '2.5rem' }}>
                  {scheduleData.statistics.location_diversity_rate?.toFixed(1) || 'N/A'}%
                </div>
                <p style={{ fontSize: '0.85rem', marginTop: '8px', opacity: 0.9 }}>
                  {scheduleData.statistics.employees_multi_location || 0} employees at multiple locations
                </p>
              </div>
              
              <div className="stat-card" style={{ background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', color: 'white' }}>
                <h3 style={{ color: 'rgba(255,255,255,0.9)' }}>Fairness Score</h3>
                <div className="value" style={{ color: 'white', fontSize: '2.5rem' }}>
                  {scheduleData.statistics.optimization_summary.fairness.score.toFixed(1)}/100
                </div>
                <p style={{ fontSize: '0.85rem', marginTop: '8px', opacity: 0.9 }}>
                  Variance: {scheduleData.statistics.optimization_summary.fairness.variance.toFixed(2)}
                </p>
              </div>
              
              <div className="stat-card" style={{ background: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', color: 'white' }}>
                <h3 style={{ color: 'rgba(255,255,255,0.9)' }}>Shift Diversity</h3>
                <div className="value" style={{ color: 'white', fontSize: '2.5rem' }}>
                  {scheduleData.statistics.avg_shift_diversity?.toFixed(1) || 'N/A'}/100
                </div>
                <p style={{ fontSize: '0.85rem', marginTop: '8px', opacity: 0.9 }}>
                  Balance across shift types
                </p>
              </div>
            </div>

            <div className="analysis-section" style={{ marginTop: '30px', background: '#f9f9f9', padding: '20px', borderRadius: '8px' }}>
              <h3>📈 Optimization Summary</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px', marginTop: '15px' }}>
                <div>
                  <strong>Fairness Distribution:</strong>
                  <ul style={{ marginTop: '5px', paddingLeft: '20px' }}>
                    <li>Min: {scheduleData.statistics.optimization_summary.fairness.min_shifts} shifts</li>
                    <li>Max: {scheduleData.statistics.optimization_summary.fairness.max_shifts} shifts</li>
                    <li>Range: {scheduleData.statistics.optimization_summary.fairness.max_shifts - scheduleData.statistics.optimization_summary.fairness.min_shifts} shifts</li>
                  </ul>
                </div>
                <div>
                  <strong>Location Distribution:</strong>
                  <ul style={{ marginTop: '5px', paddingLeft: '20px' }}>
                    <li>Multi-location employees: {scheduleData.statistics.optimization_summary.location_distribution.multi_location_employees}</li>
                    <li>Avg locations/employee: {scheduleData.statistics.optimization_summary.location_distribution.avg_per_employee.toFixed(2)}</li>
                    <li>Diversity rate: {scheduleData.statistics.optimization_summary.location_distribution.diversity_rate.toFixed(1)}%</li>
                  </ul>
                </div>
                <div>
                  <strong>Load Balancing:</strong>
                  <ul style={{ marginTop: '5px', paddingLeft: '20px' }}>
                    <li>Score: {scheduleData.statistics.optimization_summary.load_balancing.score.toFixed(1)}/100</li>
                    <li>Coefficient of Variation: {scheduleData.statistics.optimization_summary.load_balancing.coefficient_of_variation.toFixed(4)}</li>
                    <li>Conflicts: {scheduleData.statistics.conflicts_detected || 0}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* AI Analysis */}
        {scheduleData.ai_analysis && (
          <div className="ai-analysis">
            <h2>🤖 AI Analysis</h2>
            <div className="fairness-score">
              Fairness Score: {scheduleData.ai_analysis.fairness_score}/100
            </div>

            <div className="analysis-section">
              <h3>📊 Fairness Analysis</h3>
              <p style={{ 
                whiteSpace: 'pre-wrap', 
                wordBreak: 'break-word',
                color: scheduleData.ai_analysis.fairness_analysis.includes('unavailable') ? '#d32f2f' : 'inherit'
              }}>
                {scheduleData.ai_analysis.fairness_analysis}
              </p>
            </div>

            <div className="analysis-section">
              <h3>💡 Key Insights</h3>
              <p style={{ 
                whiteSpace: 'pre-wrap', 
                wordBreak: 'break-word',
                color: scheduleData.ai_analysis.insights.includes('unavailable') ? '#d32f2f' : 'inherit'
              }}>
                {scheduleData.ai_analysis.insights}
              </p>
            </div>

            <div className="analysis-section">
              <h3>⚡ Optimization Suggestions</h3>
              <p style={{ 
                whiteSpace: 'pre-wrap', 
                wordBreak: 'break-word',
                color: scheduleData.ai_analysis.optimization_suggestions.includes('unavailable') ? '#d32f2f' : 'inherit'
              }}>
                {scheduleData.ai_analysis.optimization_suggestions}
              </p>
            </div>

            <div className="analysis-section">
              <h3>📋 Schedule Explanation</h3>
              <p style={{ 
                whiteSpace: 'pre-wrap', 
                wordBreak: 'break-word',
                color: scheduleData.ai_analysis.schedule_explanation.includes('unavailable') ? '#d32f2f' : 'inherit'
              }}>
                {scheduleData.ai_analysis.schedule_explanation}
              </p>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="filters">
          <div>
            <label style={{ marginRight: '8px' }}>Date:</label>
            <select value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)}>
              <option value="all">All Dates</option>
              {scheduleData.dates.map(date => (
                <option key={date} value={date}>{date}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ marginRight: '8px' }}>Location:</label>
            <select value={selectedLocation} onChange={(e) => setSelectedLocation(e.target.value)}>
              <option value="all">All Locations</option>
              {scheduleData.locations.map(loc => (
                <option key={loc.id} value={loc.id.toString()}>{loc.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ marginRight: '8px' }}>Employee:</label>
            <select value={selectedEmployee} onChange={(e) => setSelectedEmployee(e.target.value)}>
              <option value="all">All Employees</option>
              {scheduleData.employees.map(emp => (
                <option key={emp.id} value={emp.id.toString()}>{emp.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ marginRight: '8px' }}>Shift:</label>
            <select value={selectedShift} onChange={(e) => setSelectedShift(e.target.value)}>
              <option value="all">All Shifts</option>
              {scheduleData.shifts.map(shift => (
                <option key={shift.id} value={shift.id.toString()}>{shift.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Schedule Table */}
        <div className="schedule-table">
          <div style={{ padding: '15px 20px', background: '#f9f9f9', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>Total: {totalItems} assignments</strong>
              <span style={{ marginLeft: '15px', color: '#666' }}>
                Showing {startIndex + 1} - {Math.min(endIndex, totalItems)} of {totalItems}
              </span>
            </div>
            <div style={{ color: '#666', fontSize: '0.9rem' }}>
              Page {currentPage} of {totalPages}
            </div>
          </div>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Location</th>
                  <th>Shift</th>
                  <th>Time</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {paginatedSchedule.map((assignment, idx) => (
                  <tr key={`${assignment.date}-${assignment.employee_id}-${assignment.shift_id}-${idx}`}>
                    <td className="employee-name">{assignment.employee_name}</td>
                    <td className="location-name">{assignment.location_name}</td>
                    <td>
                      <span className={`shift-badge ${getShiftBadgeClass(assignment.shift_name)}`}>
                        {assignment.shift_name}
                      </span>
                    </td>
                    <td>{assignment.start_time} - {assignment.end_time}</td>
                    <td className="date-header">
                      {new Date(assignment.date).toLocaleDateString('en-US', { 
                        weekday: 'short', 
                        year: 'numeric', 
                        month: 'short', 
                        day: 'numeric' 
                      })}
                    </td>
                  </tr>
                ))}
                {paginatedSchedule.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                      No assignments found matching the selected filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="pagination">
              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
              >
                ← Previous
              </button>
              
              <div className="pagination-numbers">
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter(page => {
                    // Show first page, last page, current page, and pages around current
                    return (
                      page === 1 ||
                      page === totalPages ||
                      (page >= currentPage - 2 && page <= currentPage + 2)
                    )
                  })
                  .map((page, idx, arr) => {
                    // Add ellipsis if there's a gap
                    const showEllipsisBefore = idx > 0 && page - arr[idx - 1] > 1
                    return (
                      <span key={page}>
                        {showEllipsisBefore && <span className="pagination-ellipsis">...</span>}
                        <button
                          className={`pagination-number ${currentPage === page ? 'active' : ''}`}
                          onClick={() => setCurrentPage(page)}
                        >
                          {page}
                        </button>
                      </span>
                    )
                  })}
              </div>
              
              <button
                className="pagination-btn"
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
              >
                Next →
              </button>
            </div>
          )}
        </div>

        <div style={{ marginTop: '40px', padding: '20px', background: 'white', borderRadius: '8px', textAlign: 'center', color: '#666' }}>
          <p>HRM Scheduling System - Built with OR-Tools & OpenAI API</p>
        </div>
      </div>
    </>
  )
}
