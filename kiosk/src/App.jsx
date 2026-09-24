import React, { useEffect, useState } from 'react';
import './index.css';

export default function App() {
  const [launches, setLaunches] = useState([]);
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(new Date());

  // Таймер времени
  useEffect(() => {
    const timerId = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timerId);
  }, []);

  // Горячая клавиша F для полноэкранного режима
  useEffect(() => {
    const onKey = (e) => {
      if (e.code === 'KeyF' || e.key.toLowerCase() === 'f' || e.key.toLowerCase() === 'а') {
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(err => console.error(err));
        } else {
          if (document.exitFullscreen) document.exitFullscreen();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Фетч данных
  useEffect(() => {
    const fetchData = async () => {
      try {
        let launchesRes = await fetch('/v1/launches/upcoming?limit=20').catch(() => null);
        if (!launchesRes || !launchesRes.ok) {
          launchesRes = await fetch('https://uttg.oxis.cc/v1/launches/upcoming?limit=20').catch(() => null);
        }

        let weatherRes = await fetch('/v1/space-weather/overview').catch(() => null);
        if (!weatherRes || !weatherRes.ok) {
          weatherRes = await fetch('https://uttg.oxis.cc/v1/space-weather/overview').catch(() => null);
        }

        if (launchesRes && launchesRes.ok) {
          const lData = await launchesRes.json();
          // Если API вернуло пустой список (нет миссий в БД), подставляем моки для демо
          setLaunches(lData.data && lData.data.length > 0 ? lData.data : mockLaunches);
        } else {
          setLaunches(mockLaunches);
        }

        if (weatherRes && weatherRes.ok) {
          const wData = await weatherRes.json();
          setWeather(wData.data && wData.data.kp_index !== null ? wData.data : mockSpaceWeather);
        } else {
          setWeather(mockSpaceWeather);
        }
      } catch (e) {
        setLaunches(mockLaunches);
        setWeather(mockSpaceWeather);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const intervalId = setInterval(fetchData, 60000);
    return () => clearInterval(intervalId);
  }, []);

  if (loading) {
    return <div className="deck"><div className="slide"><div className="sh"><span className="sh-brand">ЕШКТ</span></div></div></div>;
  }

  const nextLaunch = launches.length > 0 ? launches[0] : null;
  const subsequentLaunches = launches.slice(1, 15);

  let countdownStr = "00ч 00м 00с";
  if (nextLaunch) {
    const launchTime = new Date(nextLaunch.window_start);
    const diff = launchTime - now;
    if (diff > 0) {
      const h = Math.floor(diff / (1000 * 60 * 60));
      const m = Math.floor((diff / (1000 * 60)) % 60);
      const s = Math.floor((diff / 1000) % 60);
      countdownStr = `${String(h).padStart(2, '0')}ч ${String(m).padStart(2, '0')}м ${String(s).padStart(2, '0')}с`;
    } else {
      countdownStr = "Запуск (Liftoff)";
    }
  }

  const ruFormatter = new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Europe/Moscow',
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });

  return (
    <div className="deck" onDoubleClick={() => {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen();
      else document.exitFullscreen();
    }}>
      <div className="slide">
        <div className="sh">
          <span className="sh-brand">ЕШКТ // Дашборд</span>
        </div>
        <div className="layout-standard" style={{ padding: '100px 40px 40px 40px' }}>
          <div className="bento-grid" style={{ gridTemplateRows: '2fr 1fr' }}>
            
            <div className="bento-card col-2 accent" style={{ display: 'flex', flexDirection: 'column' }}>
              <h3>До старта осталось:</h3>
              <div className="huge-val" style={{ fontSize: '72px', margin: 'auto 0' }}>{countdownStr}</div>
              <div>
                <h4 style={{ fontSize: '28px', color: '#fff', marginBottom: '8px' }}>{nextLaunch?.name || 'Unknown Mission'}</h4>
                <p style={{ color: 'rgba(255,255,255,0.9)', fontSize: '22px', lineHeight: '1.4' }}>
                  Провайдер: {nextLaunch?.provider || 'Н/Д'}<br/>
                  Старт окна: {nextLaunch ? ruFormatter.format(new Date(nextLaunch.window_start)) : ''}<br/>
                  Погода на старте: <span style={{ color: nextLaunch?.weather_summary?.includes('Н/Д') ? 'inherit' : '#4ade80' }}>{nextLaunch?.weather_summary || 'Н/Д'}</span>
                </p>
              </div>
            </div>

            <div className="bento-card col-2 row-2" style={{ overflowY: 'auto' }}>
              <h3>График запусков</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '24px' }}>
                {subsequentLaunches.map((launch, i) => (
                  <div key={i} style={{ padding: '16px', background: '#ffffff', border: '1px solid #e4e4e7', flexShrink: 0 }}>
                    <div style={{ fontSize: '20px', fontWeight: '600', color: 'var(--text)' }}>{launch.name}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px' }}>
                      <span style={{ color: 'var(--text-dim)' }}>{ruFormatter.format(new Date(launch.window_start))}</span>
                      <span style={{ color: 'var(--accent)', fontWeight: '500' }}>{launch.provider}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bento-card col-2" style={{ display: 'flex', flexDirection: 'column' }}>
              <h3>Космическая погода (NOAA)</h3>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: 'auto', gap: '32px' }}>
                <div style={{ fontSize: '64px' }}>🛰️</div>
                <div>
                  <div style={{ fontSize: '36px', fontWeight: '600', color: 'var(--text)' }}>
                    Kp-индекс: {weather?.kp_index ?? 'Н/Д'}
                  </div>
                  <p style={{ fontSize: '20px', marginTop: '4px' }}>
                    Солнечный ветер: {weather?.solar_wind_speed_km_s ? `${Math.round(weather.solar_wind_speed_km_s)} км/с` : 'Н/Д'}<br/>
                    Состояние: {
                      weather?.condition === 'quiet' ? 'Спокойное 🟢' :
                      weather?.condition === 'unsettled' ? 'Нестабильное 🟡' :
                      weather?.condition === 'storm' ? 'Шторм 🔴' : 'Неизвестно ⚪️'
                    }
                  </p>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}

const getMockStartTime = () => {
  const saved = localStorage.getItem('kiosk_mock_start');
  if (saved && new Date(saved) > new Date()) return saved;
  const t = new Date(Date.now() + 3 * 3600 * 1000 + 45 * 60000).toISOString();
  localStorage.setItem('kiosk_mock_start', t);
  return t;
};

const mockLaunches = [
  {
    id: "1", name: "Falcon 9 Block 5 | Starlink Group 7-2", status: "Go",
    window_start: getMockStartTime(),
    window_end: new Date(Date.now() + 4 * 3600 * 1000).toISOString(), provider: "SpaceX",
    weather_summary: "80% GO (Ясно, без осадков)"
  },
  {
    id: "2", name: "Soyuz-2.1b/Fregat | GLONASS-K2", status: "TBC",
    window_start: new Date(Date.now() + 28 * 3600 * 1000).toISOString(),
    window_end: new Date(Date.now() + 29 * 3600 * 1000).toISOString(), provider: "Roscosmos",
    weather_summary: "Н/Д"
  },
  {
    id: "3", name: "Electron | The Moon God Awakens", status: "Go",
    window_start: new Date(Date.now() + 72 * 3600 * 1000).toISOString(),
    window_end: new Date(Date.now() + 74 * 3600 * 1000).toISOString(), provider: "Rocket Lab",
    weather_summary: "70% GO (Ветер на высоте)"
  },
  {
    id: "4", name: "Atlas V 551 | Project Kuiper", status: "TBD",
    window_start: new Date(Date.now() + 120 * 3600 * 1000).toISOString(),
    window_end: new Date(Date.now() + 124 * 3600 * 1000).toISOString(), provider: "ULA",
    weather_summary: "Н/Д"
  },
  {
    id: "5", name: "Starship | Flight 6", status: "TBD",
    window_start: new Date(Date.now() + 240 * 3600 * 1000).toISOString(),
    window_end: new Date(Date.now() + 241 * 3600 * 1000).toISOString(), provider: "SpaceX",
    weather_summary: "60% GO (Облачность)"
  },
  {
    id: "6", name: "Falcon 9 Block 5 | Transporter-11", status: "Go",
    window_start: new Date(Date.now() + 300 * 3600 * 1000).toISOString(),
    window_end: new Date(Date.now() + 301 * 3600 * 1000).toISOString(), provider: "SpaceX",
    weather_summary: "90% GO (Отличная погода)"
  },
  {
    id: "7", name: "Long March 2D | Yaogan-41", status: "Go",
    window_start: new Date(Date.now() + 380 * 3600 * 1000).toISOString(),
    window_end: new Date(Date.now() + 382 * 3600 * 1000).toISOString(), provider: "CASC",
    weather_summary: "Н/Д"
  }
];

const mockSpaceWeather = {
  condition: "quiet",
  kp_index: 2.3,
  solar_wind_speed_km_s: 412
};
