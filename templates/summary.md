# Zephyr samples builder summary

## Versions:
* Zephyr: `{{ versions.zephyr }}`
* SDK: `{{ versions.sdk }}`
* Micropython: `{{ versions.micropython }}`

| Status            | Number                 |
|-------------------|------------------------|
| ✅ Built             | {{ stats.built }}      |
| ⚠️ Built (ext. mem)  | {{ stats.built_ext}}   |
| ❌ Failed            | {{ stats.failed }}     |


## Board/Sample status

{% for sample_name, boards in sample_data.items() %}

<details open><summary>
Results for {{ sample_name }}
</summary>

| Board    | Built    | Extended Memory |
|----------|----------|-----------------|
{% for item in boards -%}
| {{ item.platform }} | {{ item.success }} | {{ item.extended_memory }} |
{% endfor %}

</details>

{% endfor %}
