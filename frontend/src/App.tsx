
import Dashboard from './components/Dashboard';
import './index.css';

function App() {
  return (
    <div id="app-root" className="min-h-screen" style={{ background: 'var(--bg-base)' }}>
      {/* Ambient background orbs */}
      <div className="bg-orb bg-orb-1" />
      <div className="bg-orb bg-orb-2" />
      <div className="bg-orb bg-orb-3" />
      <div style={{ position: 'relative', zIndex: 1 }}>
        <Dashboard />
      </div>
    </div>
  );
}

export default App;
