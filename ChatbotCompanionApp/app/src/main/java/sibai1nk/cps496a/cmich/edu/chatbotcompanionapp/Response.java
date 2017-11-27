package sibai1nk.cps496a.cmich.edu.chatbotcompanionapp;

/**
 * Created by noah on 11/27/17.
 */

public class Response {

    private String message;

    public Response() {
    }

    public Response(String message) {
        this.message = message;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        String[] temp = message.split("\n");
        String tempMes = "You: " + temp[0] + "\nBot: " + temp[1];
        this.message = tempMes;
    }

}