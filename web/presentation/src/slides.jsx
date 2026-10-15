import qrDemo from "@uttg/shared/qr/demo.svg";
import qrHub from "@uttg/shared/qr/hub.svg";
import { LiveTelemetry } from "./LiveTelemetry.jsx";
import { MEASUREMENTS } from "@uttg/shared/measurements";

function Title() {
  return (
    <div className="layout">
      <h1 className="title">Единый шлюз космической телеметрии</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-4 hero">
          <div className="hero-mark">Космос как API</div>
          <p>Один REST API вместо пяти несовместимых источников: орбиты, запуски, космическая погода и астероиды.</p>
        </div>
        <div className="card c-2">
          <h3>Краснов Владислав, 10 «В»</h3>
          <p>
            МБОУ СОШ № 24, г. о. Мытищи
            <br />
            Научный руководитель: Кондратенко Николай Владимирович
          </p>
        </div>
        <div className="card c-2 split">
          <div>
            <h3>Всё вживую</h3>
            <p>hub.uttg.oxis.cc</p>
          </div>
          <img className="qr" src={qrHub} alt="QR-код на hub.uttg.oxis.cc" />
        </div>
      </div>
    </div>
  );
}

function Speaker() {
  return (
    <div className="layout">
      <h1 className="title">Опыт автора</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-2 r-2">
          <div className="big">4+ года</div>
          <h3>Fullstack-разработка</h3>
          <p>
            Сам веду проекты целиком: интерфейс, сервер, базы данных, инфраструктура и выкладка. Работающие сервисы с реальными
            пользователями.
          </p>
        </div>
        <div className="card c-2">
          <h3>Сервисы реального времени</h3>
          <p>Mitu (mitu.run): таймер спикера, экраны зала и телефоны команды показывают одно и то же время с точностью до секунды.</p>
        </div>
        <div className="card c-1">
          <h3>Языки и стек</h3>
          <p>TypeScript, Python, React, FastAPI, PostgreSQL, Redis</p>
        </div>
        <div className="card c-1">
          <h3>Инфраструктура</h3>
          <p>Docker, Kubernetes, CI/CD, мониторинг и бэкапы</p>
        </div>
      </div>
    </div>
  );
}

function Relevance() {
  return (
    <div className="layout">
      <h1 className="title">Актуальность: у каждого источника свои правила</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-2 r-2">
          <div className="big">5 источников</div>
          <h3>Пять форматов и пять лимитов</h3>
          <p>
            Чтобы показать на одном экране МКС, ближайший старт и магнитную бурю, нужно написать пять интеграций и самому решать, что
            делать, когда источник недоступен.
          </p>
        </div>
        <div className="card c-1">
          <h3>CelesTrak</h3>
          <p>Орбиты в текстовом формате TLE времён перфокарт</p>
        </div>
        <div className="card c-1">
          <h3>NOAA SWPC</h3>
          <p>Индекс Kp записан строкой «2M»</p>
        </div>
        <div className="card c-1">
          <h3>NASA / JPL</h3>
          <p>Таблица из массивов без имён полей</p>
        </div>
        <div className="card c-1">
          <h3>Запуски</h3>
          <p>Бесплатно — 15 запросов в час</p>
        </div>
      </div>
    </div>
  );
}

function Goal() {
  return (
    <div className="layout">
      <h1 className="title">Цель и гипотеза</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-2 r-2">
          <h3>Цель</h3>
          <p>
            Разработать шлюз, который собирает данные из разнородных открытых источников, отдаёт их в едином формате и продолжает
            работать при отказе любого источника, и проверить его на реальном сервере.
          </p>
        </div>
        <div className="card c-2 r-2">
          <h3>Гипотеза</h3>
          <p>
            Если отделить сбор данных от ответов, разбирать каждый источник проверяемой функцией и защитить сбор повторами с нарастающей
            паузой, запасными источниками и прокси, шлюз будет отвечать за десятки миллисекунд даже при недоступности части источников.
          </p>
        </div>
      </div>
    </div>
  );
}

function Architecture() {
  const steps = ["Источники", "Планировщик", "PostgreSQL + Valkey", "REST API", "Клиенты"];
  return (
    <div className="layout">
      <h1 className="title">Архитектура: сбор отдельно, ответы отдельно</h1>
      <div className="flow">
        {steps.map((step, index) => (
          <div className={`flow-step ${index === 3 ? "accent" : ""}`} key={step}>
            {step}
          </div>
        ))}
      </div>
      <div className="grid g-3 r-1">
        <div className="card c-1">
          <h3>Планировщик</h3>
          <p>Забирает данные по расписанию, соблюдает лимиты источников и при сбое переходит на запасной путь.</p>
        </div>
        <div className="card c-1">
          <h3>API не ходит наружу</h3>
          <p>Отвечает только из своей базы и кэша, поэтому скорость не зависит от того, работает ли сейчас NASA.</p>
        </div>
        <div className="card c-1">
          <h3>Единый ответ</h3>
          <p>Всегда {"{ data, meta }"}: в meta видно источники, свежесть данных и состояние каждого источника.</p>
        </div>
      </div>
    </div>
  );
}

function Sources() {
  const rows = [
    ["CelesTrak", "В JSON нет строк TLE, нужных SGP4", "Берётся формат TLE, разбор через SGP4"],
    ["CelesTrak", "Повторный запрос: 200 OK без данных", "Распознаётся как «не изменилось»"],
    ["NOAA SWPC", "Kp строкой «2M», последняя минута предварительная", "Числовое estimated_kp, диапазон 0–9"],
    ["NOAA SWPC", "Ветер от нескольких аппаратов, есть null", "Только активный аппарат"],
    ["NASA / JPL", "Строки без имён полей", "Поиск столбцов по именам"],
    ["Запуски", "15 запросов в час, разная полнота", "Цепочка: LL2 → RocketLaunch.Live"],
  ];
  return (
    <div className="layout">
      <h1 className="title">Источники данных и их разбор</h1>
      <table className="data-table">
        <thead>
          <tr>
            <th>Источник</th>
            <th>Особенность</th>
            <th>Решение в шлюзе</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([source, feature, solution]) => (
            <tr key={feature}>
              <td>{source}</td>
              <td>{feature}</td>
              <td>{solution}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Orbits() {
  return (
    <div className="layout">
      <h1 className="title">Расчёт орбит, погода и астероиды</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-2 r-2">
          <div className="big">SGP4</div>
          <h3>Стандартная модель NORAD</h3>
          <p>
            Из двух строк TLE модель восстанавливает положение спутника на любой момент. Координаты из системы TEME переводятся в широту,
            долготу и высоту WGS-84 через звёздное время Гринвича. Проверка: МКС на высоте около 420 км.
          </p>
        </div>
        <div className="card c-2">
          <h3>0 запросов в секунду</h3>
          <p>Клиент один раз получает TLE и сам считает положение {MEASUREMENTS.trackedObjects} спутников каждую секунду.</p>
        </div>
        <div className="card c-1">
          <h3>Индекс Kp</h3>
          <p>Kp = 5 — буря G1 по шкале NOAA, при ней уходит уведомление</p>
        </div>
        <div className="card c-1">
          <h3>Астероиды</h3>
          <p>Диаметр по звёздной величине: D = 1329 / √p · 10^(−H/5)</p>
        </div>
      </div>
    </div>
  );
}

function Reliability() {
  return (
    <div className="layout">
      <h1 className="title">API и устойчивость к отказам</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-2 r-2">
          <div className="big num">{MEASUREMENTS.endpoints}</div>
          <h3>операции в API</h3>
          <p>Описание OpenAPI, кэш с защитой от лавины запросов, лимиты по стоимости: 600 / 240 / 60 / 30 запросов в минуту.</p>
        </div>
        <div className="card c-1">
          <h3>Нарастающая пауза</h3>
          <p>60 с → 2 мин → 4 мин… лимиты источников не сгорают</p>
        </div>
        <div className="card c-1">
          <h3>Выключатель</h3>
          <p>5 ошибок за 5 минут — источник отдыхает 10 минут</p>
        </div>
        <div className="card c-1">
          <h3>Прокси и запасные пути</h3>
          <p>Прямое соединение остаётся запасным</p>
        </div>
        <div className="card c-1">
          <h3>Аренда задач</h3>
          <p>Сбой посреди задачи — повтор через минуты, а не часы</p>
        </div>
      </div>
    </div>
  );
}

function Security() {
  return (
    <div className="layout">
      <h1 className="title">Безопасность по умолчанию</h1>
      <div className="grid g-3 r-2">
        <div className="card accent c-1 r-2">
          <div className="big">0 IP</div>
          <h3>Адреса не хранятся</h3>
          <p>Лимиты считаются по HMAC-SHA256 от адреса с секретным ключом. Восстановить адрес нельзя.</p>
        </div>
        <div className="card c-1">
          <h3>Защита вебхуков</h3>
          <p>Нельзя направить запрос во внутреннюю сеть; тело подписывается HMAC</p>
        </div>
        <div className="card c-1">
          <h3>Изоляция</h3>
          <p>Контейнеры без root и только для чтения, база без выхода наружу</p>
        </div>
        <div className="card c-1">
          <h3>Секреты</h3>
          <p>Со слабыми или совпадающими ключами сервис не запустится</p>
        </div>
        <div className="card c-1">
          <h3>Сайты</h3>
          <p>Строгая Content-Security-Policy, всё с одного домена</p>
        </div>
      </div>
    </div>
  );
}

function Demo() {
  return (
    <div className="layout">
      <h1 className="title">Демонстрационный клиент</h1>
      <div className="grid g-4 r-2">
        <div className="card c-3 r-2 live">
          <LiveTelemetry />
        </div>
        <div className="card accent c-1 r-2 qr-card">
          <img className="qr large" src={qrDemo} alt="QR-код на demo.uttg.oxis.cc" />
          <h3>demo.uttg.oxis.cc</h3>
          <p>Глобус, запуски, погода, астероиды. Никогда не подменяет данные</p>
        </div>
      </div>
    </div>
  );
}

function Experiment() {
  return (
    <div className="layout">
      <h1 className="title">Развёртывание и экспериментальная проверка</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-2">
          <div className="big num">{MEASUREMENTS.p50Milliseconds} мс</div>
          <h3>Медиана ответа API</h3>
          <p>p95 — {MEASUREMENTS.p95Milliseconds} мс, {MEASUREMENTS.sampleSize} запросов, сервер с 1 ядром и 2 ГБ памяти</p>
        </div>
        <div className="card c-1">
          <div className="big num">2 из 6</div>
          <h3>источников блокируют адрес</h3>
          <p>Через прокси отвечают все</p>
        </div>
        <div className="card c-1">
          <div className="big num">0</div>
          <h3>ошибок при обновлении</h3>
          <p>из {MEASUREMENTS.rolloutProbeRequests} запросов во время выкладки</p>
        </div>
        <div className="card c-2">
          <h3>Docker Swarm + Caddy</h3>
          <p>Два экземпляра API, обновление без остановки с автооткатом, ежедневные проверенные бэкапы</p>
        </div>
        <div className="card c-1">
          <div className="big num">{MEASUREMENTS.propagationMilliseconds} мс</div>
          <h3>1500 спутников в браузере</h3>
        </div>
        <div className="card c-1">
          <div className="big num">{MEASUREMENTS.tests}</div>
          <h3>автотестов</h3>
        </div>
      </div>
    </div>
  );
}

function Conclusion() {
  return (
    <div className="layout">
      <h1 className="title">Заключение</h1>
      <div className="grid g-4 r-2">
        <div className="card accent c-2 r-2">
          <div className="big">Гипотеза подтвердилась</div>
          <p>
            При недоступности части источников шлюз отвечает за {MEASUREMENTS.p50Milliseconds} мс и обновляется без остановки. Все задачи
            работы выполнены.
          </p>
        </div>
        <div className="card c-2">
          <h3>Дальше</h3>
          <p>Прогноз сияний OVATION Prime, поправки за движение полюса, второй сервер</p>
        </div>
        <div className="card c-2 split">
          <div>
            <h3>hub.uttg.oxis.cc</h3>
            <p>Демо, работа, документация API и код. Спасибо!</p>
          </div>
          <img className="qr" src={qrHub} alt="QR-код на hub.uttg.oxis.cc" />
        </div>
      </div>
    </div>
  );
}

export const SLIDES = [
  { title: "Титул", Component: Title },
  { title: "Опыт автора", Component: Speaker },
  { title: "Актуальность", Component: Relevance },
  { title: "Цель и гипотеза", Component: Goal },
  { title: "Архитектура", Component: Architecture },
  { title: "Источники", Component: Sources },
  { title: "Орбиты", Component: Orbits },
  { title: "API и устойчивость", Component: Reliability },
  { title: "Безопасность", Component: Security },
  { title: "Демо", Component: Demo },
  { title: "Эксперимент", Component: Experiment },
  { title: "Заключение", Component: Conclusion },
];
