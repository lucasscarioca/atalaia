from atalaia import EvalContext, EvalSuite


class LocalAdapter:
    def invoke(self, payload):
        return {"label": str(payload["text"]).removeprefix("label:")}


suite = EvalSuite(name="sample", adapter=LocalAdapter())


@suite.case(id="example", input={"text": "label:ok"}, expected={"label": "ok"})
def check_example(ctx: EvalContext) -> None:
    actual = ctx.adapter.invoke(ctx.case.input)
    assert actual["label"] == ctx.case.expected["label"]
