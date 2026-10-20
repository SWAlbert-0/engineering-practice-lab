RealWorld Conduit API公开规格的中文选译，来源为固定提交的OpenAPI，MIT许可；这里只整理登录、注册与文章创建，不是完整需求。
已有用户通过POST /users/login提交email和password。成功返回200及用户信息；认证失败返回401；请求字段不符合要求时返回422。
新用户通过POST /users提交username、email和password。成功返回201；发生冲突返回409；请求字段不符合要求时返回422。
获取当前用户GET /user要求认证，成功返回200及用户信息；未认证返回401。
创建文章POST /articles要求认证，提交article中的title、description和body，可选tagList。成功返回201及文章；未认证返回401；字段无效返回422。
原始规格未在本段定义密码强度、登录限流、接口耗时或页面提示文案。这些条件应作为待澄清事项，不能由生成器自行补造。
