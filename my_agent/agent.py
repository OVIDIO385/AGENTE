from google.adk.agents.llm_agent import Agent
import asyncio
import inspect

class AgentAdapter:
    def __init__(self, agent):
        self._agent = agent

    async def _drain_async_generator(self, agen):
        parts = []
        try:
            async for ev in agen:
                if ev is None:
                    continue
                # extraer campos comunes de eventos
                for attr in ("text", "content", "message", "value", "payload"):
                    if hasattr(ev, attr):
                        v = getattr(ev, attr)
                        if v:
                            parts.append(str(v))
                            break
                else:
                    # fallback a representaciones simples
                    if isinstance(ev, (str, int, float, bool)):
                        parts.append(str(ev))
                    elif isinstance(ev, (list, tuple)) and ev:
                        parts.append(" ".join(map(str, ev)))
                    elif isinstance(ev, dict):
                        parts.append(str(ev.get("text") or ev.get("content") or ev))
                    else:
                        parts.append(str(ev))
        except Exception as e:
            parts.append(f"[ERROR iterando eventos: {e}]")
        return " ".join(x for x in parts if x and str(x).strip())

    def _normalize(self, res):
        try:
            if res is None:
                return ""
            if isinstance(res, (str, int, float, bool)):
                return str(res)
            if isinstance(res, (list, tuple)) and len(res) > 0:
                first = res[0]
                if hasattr(first, "text"):
                    return str(first.text)
                if isinstance(first, (str, int, float, bool)):
                    return " ".join(map(str, res))
                if isinstance(first, dict):
                    return str(first.get("text") or first.get("content") or first)
            if isinstance(res, dict):
                return str(res.get("text") or res.get("content") or res)
            for attr in ("text", "content", "message", "output", "value"):
                if hasattr(res, attr):
                    val = getattr(res, attr)
                    return str(val) if val is not None else ""
            return str(res)
        except Exception:
            return str(res)

    def run(self, text):
        # 1) Preferir run_async / run_live (devuelven async generators en esta SDK)
        for gen_name in ("run_async", "run_live"):
            gen_fn = getattr(self._agent, gen_name, None)
            if not callable(gen_fn):
                continue
            # probar llamar pasando el texto (funcionó en la inspección)
            for attempt in (text, None, {"input": text}, {"text": text}):
                try:
                    agen = gen_fn(attempt)
                    # si es async generator -> drenar
                    if asyncio.isasyncgen(agen):
                        return asyncio.run(self._drain_async_generator(agen)) or ""
                    # si es coroutine -> resolver y normalizar
                    if asyncio.iscoroutine(agen):
                        resolved = asyncio.run(agen)
                        if asyncio.isasyncgen(resolved):
                            return asyncio.run(self._drain_async_generator(resolved)) or ""
                        return self._normalize(resolved)
                    # si devuelve resultado síncrono
                    return self._normalize(agen)
                except TypeError:
                    continue
                except Exception:
                    continue

        # 2) Métodos directos tipo generate/invoke/respond/answer/ask
        for name in ("generate", "invoke", "respond", "answer", "chat", "ask", "predict", "complete", "run"):
            fn = getattr(self._agent, name, None)
            if not callable(fn):
                continue
            try:
                out = fn(text)
                if asyncio.iscoroutine(out):
                    out = asyncio.run(out)
                if asyncio.isasyncgen(out):
                    return asyncio.run(self._drain_async_generator(out)) or ""
                return self._normalize(out)
            except TypeError:
                try:
                    out = fn([text])
                    if asyncio.iscoroutine(out):
                        out = asyncio.run(out)
                    if asyncio.isasyncgen(out):
                        return asyncio.run(self._drain_async_generator(out)) or ""
                    return self._normalize(out)
                except Exception:
                    continue
            except Exception:
                continue

        # 3) Si el agente es callable
        if callable(self._agent):
            try:
                out = self._agent(text)
                if asyncio.iscoroutine(out):
                    out = asyncio.run(out)
                if asyncio.isasyncgen(out):
                    return asyncio.run(self._drain_async_generator(out)) or ""
                return self._normalize(out)
            except Exception:
                pass

        # 4) Intentar cualquier método público callable con el texto
        for name in dir(self._agent):
            if name.startswith("_"):
                continue
            target = getattr(self._agent, name, None)
            if callable(target):
                try:
                    out = target(text)
                    if asyncio.iscoroutine(out):
                        out = asyncio.run(out)
                    if asyncio.isasyncgen(out):
                        return asyncio.run(self._drain_async_generator(out)) or ""
                    return self._normalize(out)
                except TypeError:
                    continue
                except Exception:
                    continue

        raise AttributeError("No supported call method found on wrapped agent")

    def __call__(self, text):
        return self.run(text)


# crea la instancia real y envuélvela
_raw_agent = Agent(
    model='gemini-2.0-flash',
    name='root_agent',
    description='Asistente virtual de Fondecom que ayuda a empleados y usuarios en tareas administrativas y técnicas.',
    instruction='Responde con claridad, precisión y tono profesional.',
)

root_agent = AgentAdapter(_raw_agent)

if __name__ == "__main__":
    test_text = "Hola — prueba de invocación"
    print("DEBUG: _raw_agent tipo:", type(_raw_agent))
    attrs = [a for a in dir(_raw_agent) if not a.startswith("_")]
    callables = [a for a in attrs if callable(getattr(_raw_agent, a))]
    print("DEBUG: atributos públicos del _raw_agent:", attrs)
    print("DEBUG: métodos públicos callable del _raw_agent:", callables)

    for name in callables:
        fn = getattr(_raw_agent, name)
        print(f"\n=== Probando método: {name} ===")
        try:
            sig = None
            try:
                sig = inspect.signature(fn)
            except Exception:
                sig = None
            print(" signature:", sig)
            try:
                out = fn(test_text)
                print("  -> llamado con string: OK, tipo:", type(out), "repr:", repr(out))
            except Exception as e:
                print("  -> llamado con string: ERROR:", e)
        except Exception as e:
            print("  -> error invocando método:", e)

    print("\nDEBUG: fin de pruebas.")
