import { useEffect, useRef, useState } from 'react';
import { Icon } from '../components/Icon';
import { landing as L } from '../copy/landing';
import { go, prefersReduced, scrollToId, useInView } from './hooks';
import { LandingGraph, useCascade, type Cascade } from './LandingGraph';
import { Loader, useLoaderNeeded } from './Loader';
import { Cta, Defense, Footer, Gallery, Playground, Proof, Tracks } from './Sections';

function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener('scroll', on, { passive: true });
    return () => window.removeEventListener('scroll', on);
  }, []);
  return (
    <header className={`lp-nav${scrolled ? ' solid' : ''}`}>
      <button className="lp-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="Quorum, back to top">
        <span className="lp-mark">
          <Icon name="logo" size={20} />
        </span>
        Quorum
      </button>
      <nav className="lp-links" aria-label="Sections">
        {L.nav.links.map(([id, label]) => (
          <button key={id} onClick={() => scrollToId(id)}>
            {label}
          </button>
        ))}
      </nav>
      <button className="lp-pill dark" onClick={() => go('app')}>
        {L.nav.cta}
        <Icon name="conclusion" size={16} />
      </button>
    </header>
  );
}

function useHeroLoop(c: Cascade) {
  const [step, setStep] = useState(() => (prefersReduced() ? 2 : 0));
  const cRef = useRef(c);
  useEffect(() => {
    cRef.current = c;
  });
  useEffect(() => {
    if (prefersReduced()) {
      cRef.current.quarantine('f2');
      return;
    }
    let alive = true;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const at = (ms: number, fn: () => void) => timers.push(setTimeout(() => alive && fn(), ms));
    const cycle = () => {
      cRef.current.restore();
      setStep(0);
      at(2200, () => setStep(1));
      at(4000, () => {
        cRef.current.quarantine('f2');
        setStep(2);
      });
      at(9600, cycle);
    };
    cycle();
    return () => {
      alive = false;
      timers.forEach(clearTimeout);
    };
  }, []);
  return step;
}

function Hero() {
  const cascade = useCascade();
  const step = useHeroLoop(cascade);
  const caption = [L.hero.caption.healthy, L.hero.caption.poisoned, L.hero.caption.contained][step];
  const { held, rolled, rolling, cancelled } = cascade.stats;
  return (
    <section className="lp-hero" id="top">
      <p className="lp-eyebrow">
        <span className="lp-dot" aria-hidden="true" />
        {L.hero.eyebrow}
      </p>
      <h1 className="lp-h1">
        <span>{L.hero.before}</span> <span className="ghost">{L.hero.ghost}</span>
        <br />
        <span>{L.hero.after}</span>
      </h1>
      <p className="lp-lede">{L.hero.sub}</p>
      <div className="lp-cta-row">
        <button className="lp-pill dark xl" onClick={() => go('app')}>
          {L.hero.primary}
          <Icon name="conclusion" size={18} />
        </button>
        <button className="lp-pill ghost xl" onClick={() => go('app', true)}>
          <Icon name="play" size={15} />
          {L.hero.secondary}
        </button>
      </div>

      <div className="lp-window" role="img" aria-label={L.hero.windowLabel}>
        <div className="lp-window-bar">
          <i />
          <i />
          <i />
          <span className="mono">quorum / acme / commons</span>
          <span className={`lp-window-state s${step}`}>
            <b />
            {caption}
          </span>
        </div>
        <div className="lp-window-body">
          <LandingGraph cascade={cascade} theme="dark" suspect={step === 1 ? 'f2' : undefined} label={L.hero.windowLabel} />
        </div>
        <div className="lp-window-foot">
          <span>
            <b className="num">{held}</b> held
          </span>
          <span>
            <b className="num">{rolling + rolled}</b> rolling back
          </span>
          <span>
            <b className="num">{cancelled}</b> cancelled
          </span>
          <span className="grow">No later retrieval returns them.</span>
        </div>
      </div>
    </section>
  );
}

function Marquee() {
  const items = [...L.marquee, ...L.marquee];
  return (
    <div className="lp-marquee" aria-label="Built with">
      <div className="lp-marquee-track">
        {items.map((m, i) => (
          <span key={i} aria-hidden={i >= L.marquee.length}>
            <i />
            {m}
          </span>
        ))}
      </div>
    </div>
  );
}

function Problem() {
  const [active, setActive] = useState(0);
  const rows = useRef<(HTMLLIElement | null)[]>([]);
  const [ref, seen] = useInView<HTMLDivElement>(0.1);

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (es) => {
        es.forEach((e) => {
          if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.i));
        });
      },
      { rootMargin: '-42% 0px -42% 0px' },
    );
    rows.current.forEach((r) => r && io.observe(r));
    return () => io.disconnect();
  }, []);

  const stages = [new Set(['s2', 'f2']), new Set(['s2', 'f2', 'c1', 'd1']), new Set(['s2', 'f2', 'c1', 'd1', 'a1', 'a2', 'a3'])];
  const lit = stages[active] ?? stages[0]!;
  const spread = {
    bad: lit,
    phase: {},
    pulse: new Set<string>(),
    notice: null,
    stats: { held: 0, rolling: 0, rolled: 0, cancelled: 0 },
    quarantine: () => undefined,
    restore: () => undefined,
  } as Cascade;

  return (
    <section className="lp-section lp-problem" id="problem">
      <div className="lp-head">
        <p className="lp-tag">
          <span>[{L.problem.tag}]</span> {L.problem.kicker}
        </p>
        <h2 className={`lp-h2 reveal${seen ? ' in' : ''}`} ref={ref}>
          {L.problem.title}
        </h2>
      </div>
      <div className="lp-problem-grid">
        <ol className="lp-spy">
          {L.problem.rows.map((r, i) => (
            <li key={r.h} data-i={i} ref={(el) => (rows.current[i] = el)} className={active === i ? 'on' : ''}>
              <span className="lp-spy-no mono">0{i + 1}</span>
              <h3>{r.h}</h3>
              <p>{r.p}</p>
            </li>
          ))}
        </ol>
        <div className="lp-sticky">
          <div className="lp-card-dark">
            <LandingGraph cascade={spread} theme="dark" lit={lit} label={L.problem.visualLabel} />
          </div>
        </div>
      </div>
    </section>
  );
}

export function Landing({ onEnter }: { onEnter?: () => void }) {
  const [loading, setLoading] = useState(useLoaderNeeded());
  void onEnter;
  return (
    <div className="lp">
      <a className="lp-skip" href="#lp-main" onClick={(e) => (e.preventDefault(), scrollToId('lp-main'))}>
        {L.skip}
      </a>
      {loading && <Loader onDone={() => setLoading(false)} />}
      <div className="lp-frame" aria-hidden="true">
        <i className="crop tl" />
        <i className="crop tr" />
        <i className="crop bl" />
        <i className="crop br" />
      </div>
      <Nav />
      <main id="lp-main">
        <Hero />
        <Marquee />
        <Problem />
        <Playground />
        <Defense />
        <Gallery />
        <Proof />
        <Tracks />
        <Cta />
      </main>
      <Footer />
    </div>
  );
}
